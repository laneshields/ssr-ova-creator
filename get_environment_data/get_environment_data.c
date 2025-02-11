#define _GNU_SOURCE

#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <linux/vm_sockets.h>
#include <unistd.h>
#include <arpa/inet.h>

#define SOCKET_ERROR (-1)

#define RPCI_PORT 976
#define VMX_CID 0

#define GUESTRPCPKT_FIELD_TYPE 1
#define GUESTRPCPKT_TYPE_DATA 1
#define GUESTRPCPKT_FIELD_PAYLOAD 2

void convert_ints_to_bytes(int *arr, size_t len, char *bytes) {
    for (size_t i = 0; i < len; i++) {
        uint32_t big_endian_value = htonl(arr[i]);
        memcpy(&bytes[i * 4], &big_endian_value, 4);  // Copy each integer as 4 bytes
    }
}

bool Socket_Recv(int fd, char *buf, int len) {
    int remaining = len;
    int sysErr;

    while (remaining > 0) {
        int rv = recv(fd, buf, remaining, 0);
        if (rv == 0) {
            return false;
        }
        if (rv == SOCKET_ERROR) {
            return false;
        }
        remaining -= rv;
        buf += rv;
    }

    return true;
}

int main() {

    // convert the command into bytes
    char const reqFmt[] = "%s";
    char command[] = "info-get guestinfo.ovfenv";
    char *payload = NULL;
    int payloadLen;
    payloadLen = asprintf(&payload, reqFmt, command);

    // Create the header data, unsure as to all the intricacies
    int num_elements = 8;             // these two are sloppy
    int headerLen = num_elements * 4; // but this is all fixed values

    // Was able to determine some aspects of the protocol but not all
    // the constants here seem to work consistently
    int header_values[] = {
        headerLen + payloadLen - 4, //this appears to be "remaining length"
        1,
        GUESTRPCPKT_FIELD_TYPE,
        GUESTRPCPKT_TYPE_DATA,
        0,
        2,
        GUESTRPCPKT_FIELD_PAYLOAD,
        payloadLen
    };

    char *header = malloc(headerLen);
    if (!header) {
        perror("Failed to allocate memory for header");
        return 1;
    }
    convert_ints_to_bytes(header_values, num_elements, header);

    // Combine the header and payload into a message
    size_t total_len = headerLen + payloadLen;
    char *message = malloc(total_len);
    if (!message) {
        perror("Failed to allocate memory for message");
        return 1;
    }

    memcpy(message, header, headerLen);
    memcpy(message + headerLen, payload, payloadLen);

    free(header);

    int sock;
    struct sockaddr_vm addr;

    // Create VSOCK socket
    sock = socket(AF_VSOCK, SOCK_STREAM, 0);
    if (sock < 0) {
        perror("Error creating");
        return 2;
    }

    memset(&addr, 0, sizeof(addr));
    addr.svm_family = AF_VSOCK;
    addr.svm_cid = VMX_CID;
    addr.svm_port = RPCI_PORT;

    // Connect to the VMX
    if (connect(sock, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("Error connecting to socket");
        close(sock);
        return 2;
    }

    if (send(sock, message, total_len, 0) < 0) {
        perror("Error sending on socket");
        close(sock);
        return 2;
    }
    free(message);

    bool ok;
    uint32_t packetLen;
    uint32_t partialPktLen;
    int packetLenSize = sizeof packetLen;
    int fullPktLen;
    char *recvBuf;

    ok = Socket_Recv(sock, (char *)&packetLen, packetLenSize);
    if (!ok) {
        perror("Error receiving initial data from socket");
        close(sock);
        return 2;
    }

    partialPktLen = ntohl(packetLen);
    fullPktLen = partialPktLen + packetLenSize;
    recvBuf = malloc(fullPktLen);
    if (recvBuf == NULL) {
        perror("Failed to allocate memory for recvBuf");
        close(sock);
        return 1;
    }

    memcpy(recvBuf, &packetLen, packetLenSize);
    ok = Socket_Recv(sock, recvBuf + packetLenSize, fullPktLen - packetLenSize);
    if (!ok) {
        perror("Error receiving data from socket");
        close(sock);
        return 2;
    }

    // let's just forget about the reply header since we don't need any info from it
    char *replyPayload = recvBuf + 16;
    int replyPayloadLen = fullPktLen - 16;

    char rpcReturnCode = replyPayload[0];
    if (rpcReturnCode != '1') {
        char errmsg[100];
        sprintf(errmsg, "RPC Return Code was not success, instead received: %c", rpcReturnCode);
        perror(errmsg);
        return 3;
    }

    char *replyData = replyPayload + 2; // skip return code and space
    int replyDataLen = replyPayloadLen - 2;
    printf("%s\n", replyData);

    // Clean up
    free(recvBuf);
    close(sock);
    return 0;
}
