this_dir=$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")
cd "$this_dir"
[ ! -d venv ] && python3 -m venv venv
source venv/bin/activate
export PYTHONPATH="$this_dir/src:$PYTHONPATH"
echo "Bash env ready. Run 'source venv/bin/activate' to activate venv."
