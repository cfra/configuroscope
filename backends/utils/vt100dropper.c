#define _GNU_SOURCE 1

#include <pty.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <termios.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <signal.h>

#include <event.h>

enum parsing_state {
	PARSE_DATA = 0,
	PARSE_CTRL,
	PARSE_CTRL_PARAM,
};

struct pty_child {
	int fd;
	pid_t pid;

	struct bufferevent *pty_be;
	struct bufferevent *stdin_be;
	struct bufferevent *stdout_be;

	struct event *kill_timeout;
	struct event *flush_timeout;
	struct evbuffer *linebuf;
	enum parsing_state vt_state;
};

static void pty_child_pty_read(struct bufferevent *be, void *arg)
{
	struct pty_child *pc = arg;
	unsigned char buf;

	while (evbuffer_remove(be->input, &buf, sizeof(buf))) {
		switch (pc->vt_state) {
		case PARSE_DATA:
			if (buf == '\033') {
				pc->vt_state = PARSE_CTRL;
			} else if (buf == '\n' || buf == '\r') {
				if (bufferevent_write_buffer(pc->stdout_be,
								pc->linebuf)
					|| bufferevent_write(pc->stdout_be,
								&buf, sizeof(buf)))
					event_loopbreak();
			} else {
				if (evbuffer_add(pc->linebuf, &buf, sizeof(buf)))
					event_loopbreak();

				struct timeval tv = {
					.tv_sec = 0,
					.tv_usec = 250000
				};
				if (evtimer_pending(pc->flush_timeout, NULL))
					evtimer_del(pc->flush_timeout);
				evtimer_add(pc->flush_timeout, &tv);
			}
			break;
		case PARSE_CTRL:
			if (strchr("[#(", buf)) {
				pc->vt_state = PARSE_CTRL_PARAM;
			} else if (buf == 'E') {
				pc->vt_state = PARSE_DATA;
				evbuffer_drain(pc->linebuf, -1);
			} else {
				pc->vt_state = PARSE_DATA;
			}
			break;
		case PARSE_CTRL_PARAM:
			if (!strchr("0123456789?;", buf))
				pc->vt_state = PARSE_DATA;
			break;
		}
	}
}

static void pty_child_stdin_read(struct bufferevent *be, void *arg)
{
	struct pty_child *pc = arg;

	if (bufferevent_write_buffer(pc->pty_be, be->input)) {
		event_loopbreak();
	}
}

static void pty_child_stdin_error(struct bufferevent *be, short what, void *arg)
{
	struct pty_child *pc = arg;

	if (pc->pid < 0)
		return;

	struct timeval tv = {
		.tv_sec = 0,
		.tv_usec = 500000
	};

	if (evtimer_add(pc->kill_timeout, &tv)) {
		kill(pc->pid, SIGHUP);
		event_loopbreak();
	}
}

static void pty_child_kill_timeout(int fd, short what, void *arg)
{
	struct pty_child *pc = arg;

	if (pc->pid < 0) {
		event_loopbreak();
		return;
	}

	kill(pc->pid, SIGHUP);
	event_loopbreak();
}

static void pty_child_flush_timeout(int fd, short what, void *arg)
{
	struct pty_child *pc =arg;

	if (bufferevent_write_buffer(pc->stdout_be, pc->linebuf))
		event_loopbreak();
}

static void pty_child_stdout_written(struct bufferevent *be, void *arg)
{
	struct pty_child *pc = arg;

	if (pc->pid == -1)
		event_loopbreak();
}

static void pty_child_stdout_error(struct bufferevent *be, short what, void *arg)
{
	event_loopbreak();
}

static void pty_child_pty_error(struct bufferevent *be, short what, void *arg)
{
	struct pty_child *pc = arg;
	pc->pid = -1;

	struct timeval tv = {
		.tv_sec = 0,
		.tv_usec = 500000
	};

	if (evtimer_add(pc->kill_timeout, &tv)) {
		kill(pc->pid, SIGHUP);
		event_loopbreak();
	}
}

static struct pty_child *pty_child_create(char **argv)
{
	struct pty_child *pc;

	pc = calloc(sizeof(*pc), 1);
	if (!pc) {
		perror("Could not allocate memory");
		return NULL;
	}
	
	pc->pid = forkpty(&pc->fd, NULL, NULL, NULL);
	if (pc->pid < 0) {
		perror("forkpty failed");
		return NULL;
	}

	if (!pc->pid) {
		execvp(*argv, argv);
		perror("execvp failed");
		exit(1);
	}

	pc->pty_be = bufferevent_new(pc->fd, pty_child_pty_read, NULL,
			pty_child_pty_error, pc);
	if (!pc->pty_be) {
		perror("could not create pty read event");
		return NULL;
	}

	if (bufferevent_enable(pc->pty_be, EV_READ | EV_WRITE)) {
		perror("could not enable pty read event");
		return NULL;
	}
	pc->stdin_be = bufferevent_new(STDIN_FILENO, pty_child_stdin_read, NULL,
			pty_child_stdin_error, pc);
	if (!pc->stdin_be) {
		perror("could not create stdin read event");
		return NULL;
	}

	if (bufferevent_enable(pc->stdin_be, EV_READ)) {
		perror("could not enable stdin read event");
		return NULL;
	}

	pc->stdout_be = bufferevent_new(STDOUT_FILENO, NULL,
			pty_child_stdout_written, pty_child_stdout_error, pc);
	if (!pc->stdout_be) {
		perror("could not create stdout write event");
		return NULL;
	}

	if (bufferevent_enable(pc->stdout_be, EV_WRITE)) {
		perror("could not enable stdout write event");
		return NULL;
	}

	pc->kill_timeout = malloc(sizeof(struct event));
	if (!pc->kill_timeout) {
		perror("could not create pc timeout event");
		return NULL;
	}
	evtimer_set(pc->kill_timeout, pty_child_kill_timeout, pc);

	pc->flush_timeout = malloc(sizeof(struct event));
	if (!pc->flush_timeout) {
		perror("could not create pc timeout event");
		return NULL;
	}
	evtimer_set(pc->flush_timeout, pty_child_flush_timeout, pc);

	pc->linebuf = evbuffer_new();
	if (!pc->linebuf) {
		perror("Could not create linebuf");
		return NULL;
	}

	return pc;
}

int main(int argc, char **argv)
{
	if (argc < 2) {
		fprintf(stderr, "Usage: %s <program> [<args> ...]\n", argv[0]);
		return 1;
	}

	if (!event_init()) {
		fprintf(stderr, "Could not initialize libevent\n");
		return 1;
	}

	struct pty_child *pc = pty_child_create(&argv[1]);
	if (!pc) {
		fprintf(stderr, "Creation of pty child failed\n");
		return 1;
	}

	struct termios orig, raw;

	if (tcgetattr(STDIN_FILENO, &orig)) {
		perror("Could not get terminal attributes");
		return 1;
	}

	memcpy(&raw, &orig, sizeof(raw));
	raw.c_iflag &= ~(BRKINT | INPCK | ICRNL | ISTRIP | IXON);
	raw.c_oflag &= ~(OPOST);
	raw.c_cflag &= ~(CSIZE | PARENB);
	raw.c_cflag |= CS8;
	raw.c_lflag &= ~(ECHO | ICANON | IEXTEN);
	raw.c_lflag |= ISIG;
	raw.c_cc[VMIN] = 1;
	raw.c_cc[VTIME] = 0;

	if (tcsetattr(STDIN_FILENO, TCSANOW, &raw)) {
		perror("Could not set terminal to canonical mode");
		return 1;
	}

	event_dispatch();
	close(pc->fd);
	if (pc->pid >= 0)
		kill(pc->pid, SIGTERM);
	usleep(200000);
	if (pc->pid >= 0)
		kill(pc->pid, SIGKILL);
	tcsetattr(STDIN_FILENO, TCSANOW, &orig);
	return 0;
}
