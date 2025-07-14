import shutil
import sys


def main():
    builtins = {"echo", "exit", "type"}
    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()

        try:
            line = input()
            parts = line.strip().split()
            if not parts:
                continue  # Ignore empty input

            cmd = parts[0]
            args = parts[1:]

            if cmd == "type":
                if args:
                    try:
                        arg_cmd = str(args[0])
                        if arg_cmd in builtins:
                            out = f"{arg_cmd} is a shell builtin"
                        elif p := shutil.which(arg_cmd):
                            out = f"{arg_cmd} is {p}"
                        else:
                            out = f"{arg_cmd}: not found"
                    except Exception:
                        out = f"{args[0]}: unable to read argument to type command"
                else:
                    out = "argument required after type command"
                print(out)

            elif cmd == "echo":
                if args:
                    print(" ".join(args))
                else:
                    print("")

            elif cmd == "exit":
                status = 0  # Default exit code
                if args:
                    try:
                        status = int(args[0])
                    except ValueError:
                        print(f"exit: {args[0]}: numeric argument required")
                        status = 1
                sys.exit(status)

            else:
                print(f"{cmd}: command not found")
        except EOFError:
            break


if __name__ == "__main__":
    main()