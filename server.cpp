#include <iostream>
#include <thread>
#include <vector>
#include <cstring>
#include <cstdlib>
#include <unistd.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <csignal>
#include <sys/wait.h>
#include <mutex>
#include <semaphore.h>

#define PORT 8080
//mutex used to protect access to child PID vector
std::vector<pid_t> child_pids;
std::mutex pid_mutex;  
sem_t connection_sem;

void handle_sigchld(int) {
    // Cleanup finished child processes to avoid zombies
    while (waitpid(-1, nullptr, WNOHANG) > 0);
}
// Function to handle match making between two clients 
void match_handler(int client1, int client2) {
    std::cout << "[Server] Starting new match: " << client1 << " vs " << client2 << "\n";

    send(client1, "ROLE:WHITE", strlen("ROLE:WHITE"), 0);
    send(client2, "ROLE:BLACK", strlen("ROLE:BLACK"), 0);

    fd_set readfds; //used with select to keep track of client messages
    char buffer[1024];

    while (true) {
        FD_ZERO(&readfds);
        FD_SET(client1, &readfds);
        FD_SET(client2, &readfds);
        int max_sd = std::max(client1, client2) + 1;

        int activity = select(max_sd, &readfds, nullptr, nullptr, nullptr);
        if (activity < 0) continue;

        for (int i = 0; i < 2; ++i) {
            int sender = (i == 0) ? client1 : client2;
            int receiver = (i == 0) ? client2 : client1;

            if (FD_ISSET(sender, &readfds)) {
                int bytes = recv(sender, buffer, sizeof(buffer), 0);
                if (bytes <= 0) {
                    std::cout << "[Match] Player disconnected. Ending match.\n";
                    close(client1);
                    close(client2);
                    return;
                }
                send(receiver, buffer, bytes, 0);
            }
        }
    }
}

void cleaner(bool wait_for_cleanup) {
    if (wait_for_cleanup) sleep(1);
    std::lock_guard<std::mutex> lock(pid_mutex);
    for (pid_t pid : child_pids) {
        int status;
        waitpid(pid, &status, 0);
    }
    child_pids.clear();
}

int main() {
    signal(SIGCHLD, handle_sigchld);
    sem_init(&connection_sem, 0, 1); // Initiate semaphore for match handling 

    int server_fd = socket(AF_INET, SOCK_STREAM, 0); //connect clients to server 
    sockaddr_in address{};
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(PORT);

    bind(server_fd, (sockaddr*)&address, sizeof(address));
    listen(server_fd, 10);
    std::cout << "[Server] Listening on port " << PORT << "...\n";
    // Game matching loop, that creates processes and cleaner threads 
    while (true) {
        sem_wait(&connection_sem);

        int client1 = accept(server_fd, nullptr, nullptr);
        std::cout << "[Server] New player connected: socket " << client1 << "\n";

        int client2 = accept(server_fd, nullptr, nullptr);
        std::cout << "[Server] New player connected: socket " << client2 << "\n";

        pid_t pid = fork();
        if (pid == 0) {
            close(server_fd);
            match_handler(client1, client2);
            exit(0);
        } else {
            close(client1);
            close(client2);
            {
                std::lock_guard<std::mutex> lock(pid_mutex);
                child_pids.push_back(pid);
            }
            std::thread(cleaner, true).detach();
        }

        sem_post(&connection_sem);
    }

    sem_destroy(&connection_sem);
    return 0;
}
