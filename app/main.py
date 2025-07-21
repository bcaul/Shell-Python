import shutil
import sys
import subprocess
import os
import shlex
import readline

tab_state = {"last_prefix": "", "tab_count": 0, "matches": []}

def get_executable_completions(prefix):
    builtins = ["echo", "exit", "type", "pwd", "cd"]
    completions = [cmd for cmd in builtins if cmd.startswith(prefix)]
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    seen = set(completions)
    for dir in path_dirs:
        if not os.path.isdir(dir):
            continue
        try:
            for fname in os.listdir(dir):
                if fname.startswith(prefix):
                    full_path = os.path.join(dir, fname)
                    if os.access(full_path, os.X_OK) and fname not in seen:
                        completions.append(fname)
                        seen.add(fname)
        except Exception:
            continue
    return completions

def completer(text, state):
    global tab_state
    matches = get_executable_completions(text)
    # Track tab presses and prefix
    if tab_state["last_prefix"] != text:
        tab_state["last_prefix"] = text
        tab_state["tab_count"] = 1
        tab_state["matches"] = matches
    else:
        tab_state["tab_count"] += 1

    if len(matches) == 1:
        tab_state["tab_count"] = 0
        return matches[0] + " "
    elif len(matches) > 1:
        if tab_state["tab_count"] == 1:
            # First TAB: ring bell
            sys.stdout.write('\a')
            sys.stdout.flush()
            return None
        elif tab_state["tab_count"] == 2:
            # Second TAB: print all matches
            sys.stdout.write("\n" + "  ".join(matches) + "\n$ " + text)
            sys.stdout.flush()
            tab_state["tab_count"] = 0
            return None
        else:
            return None
    return None


def main():
    builtins = {"echo", "exit", "type", "pwd", "cd"}
    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")
    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()

        try:
            line = input()
            parts = shlex.split(line, posix=True)
            if not parts:
                continue

            # Output redirection support
            if ">" in parts or "1>" in parts:
                if ">" in parts:
                    op_index = parts.index(">")
                else:
                    op_index = parts.index("1>")
                cmd_parts = parts[:op_index]
                outfile = parts[op_index + 1] if len(parts) > op_index + 1 else None
                if not outfile:
                    print("No output file specified for redirection", file=sys.stderr)
                    continue
                cmd = cmd_parts[0]
                args = cmd_parts[1:]
                with open(outfile, "w") as f:
                    if cmd in builtins:
                        # Only echo and pwd produce output
                        if cmd == "echo":
                            print(" ".join(args), file=f)
                        elif cmd == "pwd":
                            print(shutil.os.getcwd(), file=f)
                        else:
                            # For other builtins, just run as normal (no output redirection needed)
                            if cmd == "exit":
                                status = 0
                                if args:
                                    try:
                                        status = int(args[0])
                                    except ValueError:
                                        print(f"exit: {args[0]}: numeric argument required", file=sys.stderr)
                                        status = 1
                                sys.exit(status)
                            elif cmd == "cd":
                                if args:
                                    target = args[0]
                                    if target == "~":
                                        target = os.environ.get("HOME", "")
                                    try:
                                        shutil.os.chdir(target)
                                    except FileNotFoundError:
                                        print(f"cd: {args[0]}: No such file or directory", file=sys.stderr)
                                    except PermissionError:
                                        print(f"cd: {args[0]}: Permission denied", file=sys.stderr)
                                else:
                                    print("cd: missing argument", file=sys.stderr)
                            elif cmd == "type":
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
                                print(out, file=f)
                    else:
                        executable = shutil.which(cmd)
                        if executable:
                            try:
                                subprocess.run([cmd] + args, stdout=f, stderr=sys.stderr)
                            except Exception as e:
                                print(f"Error executing {cmd}: {e}", file=sys.stderr)
                        else:
                            print(f"{cmd}: command not found", file=sys.stderr)
                continue  # Skip normal command handling

            # Output redirection support for errors
            if "2>" in parts:
                op_index = parts.index("2>")
                cmd_parts = parts[:op_index]
                errfile = parts[op_index + 1] if len(parts) > op_index + 1 else None
                if not errfile:
                    print("No error file specified for redirection", file=sys.stderr)
                    continue
                cmd = cmd_parts[0]
                args = cmd_parts[1:]
                with open(errfile, "w") as ef:
                    if cmd in builtins:
                        # Only echo and pwd produce output, errors go to ef
                        if cmd == "echo":
                            print(" ".join(args))
                        elif cmd == "pwd":
                            print(shutil.os.getcwd())
                        else:
                            if cmd == "exit":
                                status = 0
                                if args:
                                    try:
                                        status = int(args[0])
                                    except ValueError:
                                        print(f"exit: {args[0]}: numeric argument required", file=ef)
                                        status = 1
                                sys.exit(status)
                            elif cmd == "cd":
                                if args:
                                    target = args[0]
                                    if target == "~":
                                        target = os.environ.get("HOME", "")
                                    try:
                                        shutil.os.chdir(target)
                                    except FileNotFoundError:
                                        print(f"cd: {args[0]}: No such file or directory", file=ef)
                                    except PermissionError:
                                        print(f"cd: {args[0]}: Permission denied", file=ef)
                                else:
                                    print("cd: missing argument", file=ef)
                            elif cmd == "type":
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
                    else:
                        executable = shutil.which(cmd)
                        if executable:
                            try:
                                subprocess.run([cmd] + args, stdout=sys.stdout, stderr=ef)
                            except Exception as e:
                                print(f"Error executing {cmd}: {e}", file=ef)
                        else:
                            print(f"{cmd}: command not found", file=ef)
                continue  # Skip normal command handling

            # Output append support
            if ">>" in parts or "1>>" in parts:
                if ">>" in parts:
                    op_index = parts.index(">>")
                else:
                    op_index = parts.index("1>>")
                cmd_parts = parts[:op_index]
                outfile = parts[op_index + 1] if len(parts) > op_index + 1 else None
                if not outfile:
                    print("No output file specified for append redirection", file=sys.stderr)
                    continue
                cmd = cmd_parts[0]
                args = cmd_parts[1:]
                with open(outfile, "a") as f:
                    if cmd in builtins:
                        if cmd == "echo":
                            print(" ".join(args), file=f)
                        elif cmd == "pwd":
                            print(shutil.os.getcwd(), file=f)
                        else:
                            if cmd == "exit":
                                status = 0
                                if args:
                                    try:
                                        status = int(args[0])
                                    except ValueError:
                                        print(f"exit: {args[0]}: numeric argument required", file=sys.stderr)
                                        status = 1
                                sys.exit(status)
                            elif cmd == "cd":
                                if args:
                                    target = args[0]
                                    if target == "~":
                                        target = os.environ.get("HOME", "")
                                    try:
                                        shutil.os.chdir(target)
                                    except FileNotFoundError:
                                        print(f"cd: {args[0]}: No such file or directory", file=sys.stderr)
                                    except PermissionError:
                                        print(f"cd: {args[0]}: Permission denied", file=sys.stderr)
                                else:
                                    print("cd: missing argument", file=sys.stderr)
                            elif cmd == "type":
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
                                print(out, file=f)
                    else:
                        executable = shutil.which(cmd)
                        if executable:
                            try:
                                subprocess.run([cmd] + args, stdout=f, stderr=sys.stderr)
                            except Exception as e:
                                print(f"Error executing {cmd}: {e}", file=sys.stderr)
                        else:
                            print(f"{cmd}: command not found", file=sys.stderr)
                continue  # Skip normal command handling

            # Append stderr support
            if "2>>" in parts:
                op_index = parts.index("2>>")
                cmd_parts = parts[:op_index]
                errfile = parts[op_index + 1] if len(parts) > op_index + 1 else None
                if not errfile:
                    print("No error file specified for append redirection", file=sys.stderr)
                    continue
                cmd = cmd_parts[0]
                args = cmd_parts[1:]
                with open(errfile, "a") as ef:
                    if cmd in builtins:
                        # Only echo and pwd produce output, errors go to ef
                        if cmd == "echo":
                            print(" ".join(args))
                        elif cmd == "pwd":
                            print(shutil.os.getcwd())
                        else:
                            if cmd == "exit":
                                status = 0
                                if args:
                                    try:
                                        status = int(args[0])
                                    except ValueError:
                                        print(f"exit: {args[0]}: numeric argument required", file=ef)
                                        status = 1
                                sys.exit(status)
                            elif cmd == "cd":
                                if args:
                                    target = args[0]
                                    if target == "~":
                                        target = os.environ.get("HOME", "")
                                    try:
                                        shutil.os.chdir(target)
                                    except FileNotFoundError:
                                        print(f"cd: {args[0]}: No such file or directory", file=ef)
                                    except PermissionError:
                                        print(f"cd: {args[0]}: Permission denied", file=ef)
                                else:
                                    print("cd: missing argument", file=ef)
                            elif cmd == "type":
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
                    else:
                        executable = shutil.which(cmd)
                        if executable:
                            try:
                                subprocess.run([cmd] + args, stdout=sys.stdout, stderr=ef)
                            except Exception as e:
                                print(f"Error executing {cmd}: {e}", file=ef)
                        else:
                            print(f"{cmd}: command not found", file=ef)
                continue  # Skip normal command handling

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
            
            elif cmd == "cd":
                if args:
                    target = args[0]
                    if target == "~":
                        target = os.environ.get("HOME", "")
                    try:
                        shutil.os.chdir(target)
                    except FileNotFoundError:
                        print(f"cd: {args[0]}: No such file or directory", file=sys.stderr)
                    except PermissionError:
                        print(f"cd: {args[0]}: Permission denied", file=sys.stderr)
                else:
                    print("cd: missing argument", file=sys.stderr)

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