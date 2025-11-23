set this_dir (dirname (readlink -f (status -f)))
cd $this_dir
if not test -d venv
    python3 -m venv venv
end
source venv/bin/activate.fish
set -gx PYTHONPATH $this_dir/src $PYTHONPATH
echo "Fish env ready. Virtualenv activated."
