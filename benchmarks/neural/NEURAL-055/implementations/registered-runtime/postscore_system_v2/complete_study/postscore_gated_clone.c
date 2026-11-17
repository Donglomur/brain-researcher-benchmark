/* Linux-only source-owned birth placement. Build/execute only after qualification.
 * clone3 CLONE_PARENT requires exit_signal=0; the child's exit signal is inherited
 * from the helper's parent relation. CLONE_INTO_CGROUP makes all child CPU/memory
 * belong to the selected leaf, including the gate and exec bootstrap.
 */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/sched.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/types.h>
#include <sys/un.h>
#include <unistd.h>

extern char **environ;
static void die(const char *what) { perror(what); _exit(125); }
int main(int argc, char **argv) {
    /* leaf, fresh observer Unix socket, then exact executable + argv. */
    if (argc < 4 || argv[1][0]!='/' || argv[2][0]!='/' || argv[3][0]!='/') return 124;
    if (strlen(argv[2]) >= sizeof(((struct sockaddr_un *)0)->sun_path)) return 124;
    int cg=open(argv[1],O_DIRECTORY|O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
    if(cg<0) die("open owned leaf");
    int ready[2];
    if(pipe2(ready,O_CLOEXEC)<0) die("owned readiness pipe");
    struct clone_args a={0};
    a.flags=CLONE_INTO_CGROUP|CLONE_PARENT;
    a.cgroup=(uint64_t)cg;
    a.exit_signal=0;
    pid_t owner=getppid();
    pid_t child=(pid_t)syscall(SYS_clone3,&a,sizeof(a));
    if(child<0) die("clone3 into owned leaf");
    if(child>0) {
        if(close(cg)<0) die("close cgroup");
        if(close(ready[1])<0) die("close readiness writer");
        char marker=0; ssize_t got;
        do { got=read(ready[0],&marker,1); } while(got<0 && errno==EINTR);
        if(got!=1 || marker!='R') die("child session readiness");
        if(close(ready[0])<0) die("close readiness reader");
        /* ProcessRunner may now require the helper's process group absent:
           the owned role child has already created its separate session. */
        if(printf("%ld\n",(long)child)<0 || fflush(stdout)!=0) die("publish original pid");
        return 0;
    }
    if(close(cg)<0 || setsid()<0 || prctl(PR_SET_PDEATHSIG,SIGKILL)<0 || getppid()!=owner)
        die("child gate bootstrap");
    if(close(ready[0])<0) die("close child readiness reader");
    if(write(ready[1],"R",1)!=1 || close(ready[1])<0) die("child session readiness acknowledgment");
    /* Never inherit launcher stdout/stderr: its ProcessRunner must close before
       the observer releases this process. The socket owns all later output. */
    int nullfd=open("/dev/null",O_RDWR);
    if(nullfd<0) _exit(125);
    for(int fd=0;fd<3;fd++) if(dup2(nullfd,fd)<0) _exit(125);
    if(nullfd>2 && close(nullfd)<0) _exit(125);
    int sock=socket(AF_UNIX,SOCK_STREAM,0);
    if(sock<0) _exit(125);
    struct sockaddr_un address={0}; address.sun_family=AF_UNIX;
    memcpy(address.sun_path,argv[2],strlen(argv[2])+1);
    if(connect(sock,(struct sockaddr*)&address,sizeof(address))<0) _exit(125);
    char gate=0; ssize_t got;
    do { got=read(sock,&gate,1); } while(got<0 && errno==EINTR);
    if(got!=1 || gate!='G') _exit(126);
    if(dup2(sock,1)<0 || dup2(sock,2)<0) _exit(125);
    if(sock>2 && close(sock)<0) _exit(125);
    execve(argv[3],argv+3,environ);
    die("exec qualified operand");
}
