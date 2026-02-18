import sys
import asyncio
from .config import load_config, setup_wizard

def main():
    cfg = load_config()
    cfg = setup_wizard(cfg)
    if "--web" in sys.argv:
        from .web.app import run_web
        run_web(cfg)
    else:
        from .cli.app import run_cli
        asyncio.run(run_cli(cfg))

if __name__ == "__main__":
    main()
