from pyscript import when, display

@when("click", "#my-button")
def handle_click():
    display("✅ Button clicked from main.py!", target="output")
