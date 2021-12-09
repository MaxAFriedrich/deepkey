import pyaudio
pa = pyaudio.PyAudio()
devices = []
for i in range(pa.get_device_count()):
    devices.append(pa.get_device_info_by_index(i))


def edit(out={
    "model": "./moz.pbmm",
    "scorer": "./moz.scorer",
    "device": 6,
    "rate": 16000,
    "padding": 3000,
    "ratio": 0.5
}):
    global devices

    model = input("Set your model. ["+out["model"]+"] ")
    if model != "":
        out["model"] = model

    scorer = input("Set your scorer. ["+out["scorer"]+"] ")
    if scorer != "":
        out["scorer"] = scorer

    print(
        "Pick a device by number (enter for current) ["+str(out["device"])+"]: ")
    for device in devices:
        print(str(device["index"])+": "+device["name"])
    device = input("")
    if device != "":
        out["device"] = int(device)

    rate = input(
        "Set your sample rate(eg. 16000, 44000). ["+str(out["rate"])+"] ")
    if rate != "":
        out["rate"] = int(rate)

    padding = input("Set your frame padding. ["+str(out["padding"])+"] ")
    if padding != "":
        out["padding"] = int(padding)

    ratio = input("Set your frame ratio. ["+str(out["ratio"])+"] ")
    if ratio != "":
        out["ratio"] = float(ratio)
    return out


def main():
    from yaml import load, dump, FullLoader
    from os.path import isfile
    if isfile("settings.yml"):
        with open("settings.yml", "r") as file:
            current = load(file.read(), Loader=FullLoader)
            print("Your current settings:\n" + dump(current))
            if input("Do you want to change them?[Y/n] ").lower() == "n":
                return
            else:
                new = edit(current)
    else:
        print("It apears you do not have a settings file. Lets create one.")
        new = edit()
    print("\n Your new settings are: \n"+dump(new))
    with open("settings.yml", "w") as file:
        file.write(dump(new))


if __name__ == '__main__':
    main()
