import shutil
import sys
import subprocess


def main():
    builtins = {"echo", "exit", "type", "pwd"}
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
                        print(f"exit: {args[0]}: numeric argument required", file=sys.stderr)
                        status = 1
                sys.exit(status)

            elif cmd == "pwd":
                print(shutil.os.getcwd())

            else:
                # Check if command exists in PATH
                executable = shutil.which(cmd)
                if executable:
                    try:
                        # Run the external program with arguments
                        subprocess.run([cmd] + args)
                    except Exception as e:
                        print(f"Error executing {cmd}: {e}")
                else:
                    print(f"{cmd}: command not found")
                    
        except EOFError:
            break


if __name__ == "__main__":
    main()