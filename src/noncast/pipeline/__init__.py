"""Pipeline stages. Import submodules (scrape, draft, …) or `today.run_today`."""

__all__ = ["run_today"]


def __getattr__(name: str):
    if name == "run_today":
        from noncast.pipeline.today import run_today

        return run_today
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
