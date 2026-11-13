"""Verify local extraction and graph access before launching the workstation."""
import sys

from backend.graph_db import Neo4jGraphDatabase
from backend.text_ner import LocalWorker, TextNERError


def main():
    worker = LocalWorker(timeout=30)
    try:
        worker.request(['EVORA runtime check.'])
    except TextNERError as error:
        print(f'Text extraction unavailable ({error.code}). Install requirements.txt into .venv.', file=sys.stderr)
        return 1
    finally:
        worker.close()
    graph = None
    try:
        graph = Neo4jGraphDatabase()
        graph.get_driver().verify_connectivity()
    except Exception:
        print('Graph unavailable. Check NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD and NEO4J_DATABASE in .env.', file=sys.stderr)
        return 1
    finally:
        if graph is not None:
            graph.close()
    from backend import plates
    if plates.model_info():
        import numpy as np
        try:
            plates.detect(np.zeros((64, 128, 3), dtype=np.uint8))
        except Exception:
            print('Plate worker unavailable. Run scripts/setup-plates.sh.', file=sys.stderr)
            return 1
        finally:
            plates.close()
    print('Text model and graph connection ready.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
