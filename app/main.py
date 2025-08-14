import shutil
import sys
import subprocess
import os
import shlex
import io

try:
    import readline
except ImportError:
    import pyreadline3 as readline

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
    return sorted(completions)

def longest_common_prefix(strings):
    if not strings:
        return ""
    prefix = strings[0]
    for s in strings[1:]:
        i = 0
        while i < len(prefix) and i < len(s) and prefix[i] == s[i]:
            i += 1
        prefix = prefix[:i]
        if not prefix:
            break
    return prefix

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

    if not matches:
        return None

    # If only one match, complete to it
    if len(matches) == 1:
        tab_state["tab_count"] = 0
        if state == 0:
            return matches[0] + " "
        else:
            return None

    # Multiple matches: complete to longest common prefix
    lcp = longest_common_prefix(matches)
    if lcp and lcp != text:
        if state == 0:
            return lcp
        else:
            return None

    # If no further completion, handle bell and list as before
    if tab_state["tab_count"] == 1:
        sys.stdout.write('\a')
        sys.stdout.flush()
        return None
    elif tab_state["tab_count"] == 2:
        sys.stdout.write("\n" + "  ".join(matches) + "\n$ " + text)
        sys.stdout.flush()
        tab_state["tab_count"] = 0
        return None
    else:
        return None

def run_builtin(cmd, args, inp=None, out=None):
    # Save original stdin/stdout
    orig_in, orig_out = sys.stdin, sys.stdout
    if inp:
        sys.stdin = inp
    if out:
        sys.stdout = out
    try:
        if cmd == "echo":
            print(" ".join(args))
        elif cmd == "pwd":
            print(shutil.os.getcwd())
        elif cmd == "type":
            if args:
                arg_cmd = str(args[0])
                if arg_cmd in builtins:
                    print(f"{arg_cmd} is a shell builtin")
                elif p := shutil.which(arg_cmd):
                    print(f"{arg_cmd} is {p}")
                else:
                    print(f"{arg_cmd}: not found")
            else:
                print("argument required after type command")
        elif cmd == "exit":
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
    finally:
        sys.stdin, sys.stdout = orig_in, orig_out

def run_pipeline(commands, builtins):
    """Run a pipeline of commands, handling built-ins and externals."""
    n = len(commands)
    prev_output = None  # For input to the next command

    for i, cmd_parts in enumerate(commands):
        cmd = cmd_parts[0]
        args = cmd_parts[1:]
        is_builtin = cmd in builtins

        # If not last command, prepare a buffer for output
        if i < n - 1:
            buf = io.StringIO()
            out = buf
        else:
            out = sys.stdout

        inp = prev_output

        if is_builtin:
            # For built-ins, use run_builtin with inp/out
            run_builtin(cmd, args, inp=inp, out=out)
        else:
            # For externals, use subprocess
            stdin = inp if inp is None else subprocess.PIPE
            stdout = out if out != sys.stdout else None
            if inp:
                # Read input from inp and pass to process
                p = subprocess.Popen([cmd] + args, stdin=subprocess.PIPE, stdout=stdout)
                input_bytes = inp.read().encode()
                out_bytes, _ = p.communicate(input=input_bytes)
                if out != sys.stdout and out is not None and out_bytes is not None:
                    out.write(out_bytes.decode())
            else:
                p = subprocess.Popen([cmd] + args, stdout=stdout)
                out_bytes, _ = p.communicate()
                if out != sys.stdout and out is not None and out_bytes is not None:
                    out.write(out_bytes.decode())

        # Prepare input for next command
        if i < n - 1:
            if out is sys.stdout:
                # Should not happen, but just in case
                prev_output = None
            else:
                out.seek(0)
                prev_output = out

def main():
    builtins = {"echo", "exit", "type", "pwd", "cd"}
    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")
    while True:
        sys.stdout.write("$ ")
        sys.stdout.flush()
        try:
            line = input()
            tab_state["last_prefix"] = ""
            tab_state["tab_count"] = 0
            tab_state["matches"] = []
            if "|" in line:
                # Split pipeline into commands
                pipeline_cmds = [shlex.split(seg.strip()) for seg in line.split("|")]
                if not all(pipeline_cmds):
                    continue
                run_pipeline(pipeline_cmds, builtins)
                continue

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