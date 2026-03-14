#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

#define STACK_MAX 1024

static int stack[STACK_MAX];
static int sp = -1; /* stack pointer, -1 = empty */

static void push(int val) {
    if (sp >= STACK_MAX - 1) {
        fprintf(stderr, "Error: stack overflow\n");
        exit(1);
    }
    stack[++sp] = val;
}

static int pop(void) {
    if (sp < 0) {
        fprintf(stderr, "Error: stack underflow\n");
        exit(1);
    }
    return stack[sp--];
}

static int peek(void) {
    if (sp < 0) {
        fprintf(stderr, "Error: stack empty\n");
        exit(1);
    }
    return stack[sp];
}

int main(int argc, char *argv[]) {
    FILE *fp;
    char *src;
    long len;
    int ip;
    int loop_positions[256];
    int loop_depth = -1;

    if (argc <= 1) {
        fprintf(stderr, "Usage: %s <source file>\n", argv[0]);
        return 1;
    }

    fp = fopen(argv[1], "r");
    if (!fp) {
        fprintf(stderr, "Error: cannot open file '%s'\n", argv[1]);
        return 1;
    }

    fseek(fp, 0, SEEK_END);
    len = ftell(fp);
    rewind(fp);
    src = (char *)malloc(len + 1);
    fread(src, 1, len, fp);
    src[len] = '\0';
    fclose(fp);

    /* Strip \r characters */
    {
        int r = 0, w = 0;
        for (r = 0; src[r]; r++) {
            if (src[r] != '\r')
                src[w++] = src[r];
        }
        src[w] = '\0';
        len = w;
    }

    for (ip = 0; ip < len; ip++) {
        char ch = src[ip];

        switch (ch) {
        case '~':
            /* Push 65 ('A') onto stack */
            push(65);
            break;

        case '(':
            /* Parse decimal number, push onto stack */
            {
                int start = ++ip;
                while (ip < len && isdigit((unsigned char)src[ip]))
                    ip++;
                {
                    char saved = src[ip];
                    src[ip] = '\0';
                    push(atoi(&src[start]));
                    src[ip] = saved;
                }
                ip--; /* will be incremented by for loop */
            }
            break;

        case '%':
            /* ADD: pop two values, push their sum */
            {
                int a = pop();
                int b = pop();
                push(a + b);
            }
            break;

        case '#':
            /* NEGATE: negate top of stack in place */
            stack[sp] = -stack[sp];
            break;

        case '!':
            /* INCREMENT: add 1 to top of stack */
            stack[sp] += 1;
            break;

        case '@':
            /* DECREMENT: subtract 1 from top of stack */
            stack[sp] -= 1;
            break;

        case '^':
            /* PRINT: output top of stack as ASCII char (NO pop) */
            /* BUG FIX #1: original compiler popped after printing */
            putchar((char)(peek() & 0xFF));
            break;

        case '$':
            /* SWAP: swap top two elements */
            /* BUG FIX #2: original compiler duplicated top twice (sp += 2) */
            if (sp >= 1) {
                int tmp = stack[sp];
                stack[sp] = stack[sp - 1];
                stack[sp - 1] = tmp;
            }
            break;

        case '`':
            /* POP: discard top of stack */
            pop();
            break;

        case '&':
            /* WHILE: if top == 0, skip to matching '*'; else save position */
            if (peek() == 0) {
                int depth = 1;
                ip++;
                while (ip < len && depth > 0) {
                    if (src[ip] == '&') depth++;
                    else if (src[ip] == '*') depth--;
                    ip++;
                }
                ip--; /* will be incremented by for loop */
            } else {
                loop_depth++;
                loop_positions[loop_depth] = ip;
            }
            break;

        case '*':
            /* END-WHILE: if top != 0, jump back to '&'; else exit loop */
            if (loop_depth < 0) {
                fprintf(stderr, "Error: unmatched *\n");
                exit(1);
            }
            if (peek() != 0) {
                ip = loop_positions[loop_depth]; /* jump back to & */
                /* the for loop will increment ip, moving past & */
            } else {
                loop_depth--;
            }
            break;

        case ')':
            /* COMMENT: skip to end of line */
            while (ip < len && src[ip] != '\n')
                ip++;
            break;

        default:
            /* Unknown characters are ignored */
            break;
        }
    }

    /* BUG FIX #3: original compiler printed '\n' (0x0a) here;
       correct behavior is to print '!' (0x21) */
    putchar('!');

    free(src);
    return 0;
}
