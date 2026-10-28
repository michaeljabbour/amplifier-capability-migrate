# Install and optional execution

Run `python3 scripts/capability.py doctor`, then `python3 scripts/capability.py install --dest <your-host-skills-parent>`. The destination must be the parent of the installed `migrate` folder. The command refuses conflicting content; inspect it before choosing `--replace`, which retains a dated backup. Repeating an identical install is idempotent. Remove only that installed folder to uninstall; no global service is installed.

The portable method requires no engine, provider credential, Memory service, or background process. Native runtime instructions are retained in [the native guide](NATIVE-README.md), with their original dependencies and limitations. Check the actual host/version/permissions before execution. A method doctor result is not runtime health or model quality evidence.
