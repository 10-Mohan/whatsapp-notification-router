import os
import zipfile
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("packager")

def package_solution():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    zip_path = os.path.join(root_dir, "code.zip")

    logger.info(f"Packaging solution into {zip_path}...")
    
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Include code directory files
        code_dir = os.path.join(root_dir, "code")
        for root, dirs, files in os.walk(code_dir):
            for file in files:
                if file.endswith((".py", ".json", ".md")):
                    full_path = os.path.join(root, file)
                    arcname = os.path.relpath(full_path, root_dir)
                    zipf.write(full_path, arcname)
                    logger.info(f"Added {arcname}")

        # Include web directory files
        web_dir = os.path.join(root_dir, "web")
        if os.path.exists(web_dir):
            for root, dirs, files in os.walk(web_dir):
                for file in files:
                    if file.endswith((".html", ".css", ".js", ".json")):
                        full_path = os.path.join(root, file)
                        arcname = os.path.relpath(full_path, root_dir)
                        zipf.write(full_path, arcname)
                        logger.info(f"Added {arcname}")

        # Include root documentation
        for doc in ["README.md", "problem_statement.md", "AGENTS.md"]:
            doc_path = os.path.join(root_dir, doc)
            if os.path.exists(doc_path):
                zipf.write(doc_path, doc)
                logger.info(f"Added {doc}")

    logger.info(f"Successfully created submission package: {zip_path}")

if __name__ == "__main__":
    package_solution()
