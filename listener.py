from pynput.keyboard import Listener

def on_press(key):
    print(key)

listener = Listener(on_press=on_press)
listener.start()
listener.join()