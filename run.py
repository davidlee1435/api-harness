import sys

from helpers import *  # noqa: F401,F403  (helpers pre-imported for -c snippets)

HELP = """API Harness

Read SKILL.md for the default workflow. Read helpers.py for the functions.
For setup, env vars, or debugging, read install.md.

Typical usage:
  api-harness -c "print(get('https://api.github.com/zen'))"
  api-harness -c "store('issues', get('https://api.github.com/repos/python/cpython/issues')); print(q('SELECT count(*) AS n FROM issues'))"

Helpers are pre-imported (request/get/post/put/delete, paginate, db/store/q, read_docs/read_sdk).
"""


def main():
    args = sys.argv[1:]
    if args and args[0] in {"-h", "--help"}:
        print(HELP)
        return
    if not args or args[0] != "-c":
        sys.exit('Usage: api-harness -c "print(get(\'https://api.github.com/zen\'))"')
    exec(args[1], globals())


if __name__ == "__main__":
    main()
