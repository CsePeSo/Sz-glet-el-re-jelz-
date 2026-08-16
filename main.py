# Small launcher: prefer Streamlit web UI (streamlit_app.py) when Streamlit is available,
# otherwise run the original console entrypoint (console_main.py).

try:
    # If Streamlit is installed in the environment, import the web UI wrapper.
    # When Streamlit runs `streamlit run main.py` it will import this file, and
    # importing streamlit_app will register the Streamlit UI.
    import streamlit  # type: ignore
    import streamlit_app  # noqa: F401
except Exception:
    # Fallback: run console main (for local CLI usage)
    try:
        from console_main import main as console_main
    except Exception:
        # If console_main missing, provide a clear error
        raise

    if __name__ == "__main__":
        console_main()
