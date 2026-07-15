from typing import Tuple
import os
import subprocess
import tempfile
import yaml


class Editor:
    def edit_yaml(self, comp_dict: dict) -> Tuple[dict, bool]:
        editor = os.environ.get("EDITOR", "vi")
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".yaml", delete=False) as tf:
            path = tf.name
            yaml.safe_dump(comp_dict, tf, sort_keys=False, allow_unicode=True, width=float('inf'))
            tf.flush()
        try:
            # Save original text
            original_text = yaml.safe_dump(comp_dict, sort_keys=False, allow_unicode=True, width=float('inf'))

            # Launch editor
            subprocess.call([editor, path])

            # Read edited text
            with open(path, "r", encoding="utf-8") as f:
                edited_text = f.read()

            if edited_text.strip() == original_text.strip():
                return comp_dict, False

            # Otherwise parse YAML and return
            edited = yaml.safe_load(edited_text)
            return edited, True

        finally:
            try:
                os.unlink(path)
            except Exception:
                pass
