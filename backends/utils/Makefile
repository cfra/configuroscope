all: vt100dropper

vt100dropper: vt100dropper.c
	gcc -o vt100dropper vt100dropper.c -std=c99 -Werror -Wall -pedantic -levent -lutil

clean:
	rm vt100dropper

.PHONY: all clean
