#!/usr/bin/env python3

import wayfire as ws
import os
import sys
import pprint
import json
import argparse
from subprocess import call, check_output, Popen
from PIL import Image, ImageFont
import psutil
import threading
import time

parser = argparse.ArgumentParser(
    description="wayctl script utility for controlling some parts of the wayfire compositor through CLI or a script."
)
parser.add_argument(
    "--view",
    nargs="*",
    help="get info about views",
)

parser.add_argument(
    "--workspace",
    nargs="*",
    help="set the focused view to another workspace",
)

parser.add_argument(
    "--dpms",
    nargs="*",
    help="set dpms on/off/toggle",
)

parser.add_argument(
    "--output",
    nargs="*",
    help="get output info",
)

parser.add_argument(
    "--screenshot",
    nargs="*",
    help="options: (output, focused, slurp), output: screenshot the whole monitor, focused: screenshot the view, slurp: select a region to screenshot",
)

parser.add_argument(
    "--session",
    nargs="*",
    help="print session",
)

parser.add_argument(
    "--resize",
    nargs="*",
    help="resize views",
)

parser.add_argument(
    "--switch",
    nargs="*",
    help="switch views side",
)


args = parser.parse_args()

arg = sys.argv[1]
sub_arg = " ".join(sys.argv[2:])


addr = os.getenv("WAYFIRE_SOCKET")
sock = ws.WayfireSocket(addr)


def view_focused():
    view = sock.get_focused_view()
    print("[{0}: {1}]".format(view["app-id"], view["title"]))
    view = json.dumps(view, indent=4)
    print(view)
    print("\n\n")


def create_new_session_file(file_path):
    try:
        # Remove the old file if it exists
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Old session '{file_path}' removed.")

        # Create a new session file
        with open(file_path, "w") as file:
            file.write("")  # You can write initial content here if needed

        print(f"New session file '{file_path}' created successfully.")
        return file_path

    except Exception as e:
        print(f"Error creating session file: {e}")
        return None


def add_cmdline(view, process):
    ws_views = sock.get_workspaces_with_views()
    for view in sock.list_views():
        if process.pid == view["pid"]:
            view["cmdline"] = process.cmdline()
            for d in ws_views:
                if d["view-id"] == view["id"]:
                    view["workspace"] = {"x": d["x"], "y": d["y"]}
            return view


def save_views_session():
    list_views = sock.list_views()
    home = os.path.expanduser("~")
    wayfire = ".config/wayfire-session.json"
    save_path = os.path.join(home, wayfire)
    create_new_session_file(save_path)
    for view in list_views:
        view = add_cmdline(view, psutil.Process(view["pid"]))
        with open(save_path, "a") as f:
            json.dump(view, f, indent=4)
            f.write("\n--------view--------\n")


def load_wayfire_session():
    home = os.path.expanduser("~")
    wayfire = ".config/wayfire-session.json"
    load_path = os.path.join(home, wayfire)
    with open(load_path, "r") as file:
        data = file.read()

    # Split the data using the separator '---SEPARATOR---'
    json_list = data.split("\n--------view--------\n")

    # Remove any empty strings
    json_list = [item for item in json_list if item]

    # Load each JSON object as a dictionary
    result = []
    for json_str in json_list:
        result.append(json.loads(json_str))

    return result


def start_app(cmdline):
    return sock.run(" ".join(cmdline))["pid"]


def start_wayfire_session():
    views = load_wayfire_session()
    for view in views:
        if "workspace" not in view:
            continue
        workspace = view["workspace"]
        sock.set_workspace(workspace)
        cmdline = view["cmdline"]
        pid = start_app(cmdline)
        time.sleep(1)

        # FIXME need a limit for that in case there is no pid at all
        while 1:
            if pid:
                break
        view_id = None
        for v in sock.list_views():
            if v["pid"] == pid:
                view_id = v["id"]
        if not view_id:
            continue

        sock.maximize(view_id)
        sock.set_workspace(workspace, view_id)
        sock.maximize(view_id)

        # x = view["geometry"]["x"]
        # y = view["geometry"]["y"]
        # w = view["geometry"]["width"]
        # h = view["geometry"]["height"]
        # sock.configure_view(view_id, x, y, w, h)


def screenshot_geometry():
    output = sock.get_focused_output()
    focused_view = sock.get_focused_view()
    ox = output["geometry"]["x"]
    oy = output["workarea"]["y"]
    vwidth = focused_view["geometry"]["width"]
    vheight = focused_view["geometry"]["height"]
    view_geometry = "{0},{1} {2}x{3}".format(ox, oy, vwidth, vheight)
    return view_geometry, focused_view


def screenshot_view_focused():
    focused = sock.get_focused_view()
    title = focused["title"]
    view_id = focused["id"]
    filename = "{0}.webp".format(title)
    screenshot_view_id(view_id, filename)
    call(["xdg-open", filename])


def screenshot_focused_output():
    sock.screenshot_focused_monitor()


def screenshot_slurp():
    focused_view = sock.get_focused_view()
    slurp = check_output(["slurp"]).decode().strip()
    title = focused_view["title"].replace(" ", "-")
    filename = "{0}.jpg".format(title)
    cmd = ["grim", "-g", "{0}".format(slurp), filename]
    call(cmd)
    call(["xdg-open", filename])


def generate_screenshot_info(view_id, filename):
    font_size = 22
    font_filepath = "SourceCodePro-ExtraLight.otf"
    color = (80, 80, 80)
    view = sock.get_view(view_id)
    text = "ID: {0}, PID: {1}, Title: {2}".format(
        view["id"], view["pid"], view["title"]
    )
    font = ImageFont.truetype(font_filepath, size=font_size)
    mask_image = font.getmask(text, "L")
    size = mask_image.size[0] + 20, mask_image.size[1] + 20
    img = Image.new("RGBA", size)
    img.im.paste(color, (20, 20) + size, mask_image)
    img.save(filename)


def screenshot_view_id(view_id, filename):
    sock.screenshot(view_id, filename)


def screenshot_all_outputs():
    sock.screenshot_all_outputs()


def screenshot_view_list():
    all_jpg = []
    for view in sock.list_views():
        view_id = view["id"]
        filename = str(view_id) + ".png"
        infofile = "info-" + filename
        infofile = os.path.join("/tmp", infofile)
        filename = os.path.join("/tmp", filename)
        generate_screenshot_info(view_id, infofile)
        sock.screenshot(view_id, filename)
        all_jpg.append((infofile, filename))
    join_all_images(all_jpg)


def join_all_images(images):
    for im in images:
        im1 = Image.open(im[0])
        im2 = Image.open(im[1])
        dst = Image.new("RGB", (im2.width, im2.height + im1.height))
        dst.paste(im1, (0, im2.height))
        dst.paste(im2, (0, 0))
        dst.save(im[1])


# def join_all_images(image_paths):
#     images = [Image.open(path) for path in image_paths]
#     min_shape = sorted([(np.sum(image.size), image.size) for image in images])[0][1]
#     horizontal_concatenation = np.hstack([image for image in images])
#
#     horizontal_concatenation = Image.fromarray(horizontal_concatenation)
#     horizontal_concatenation.save("view.png")
#
#     vertical_concatenation = np.vstack([image.resize(min_shape) for image in images])
#     vertical_concatenation = Image.fromarray(vertical_concatenation)
#     vertical_concatenation.save("all_views.png")


def resize_views_left():
    sock.resize_views_left()


def resize_views_right():
    sock.resize_views_right()


def resize_views_up():
    sock.resize_views_up()


def resize_views_down():
    sock.resize_views_down()


def switch_views_side():
    sock.switch_views_side()


def dpms():
    if "on" in args.dpms:
        monitor_name = args.dpms[-1].strip()
        sock.dpms("on", monitor_name)
    if "off" in args.dpms:
        monitor_name = args.dpms[-1].strip()
        sock.dpms("off", monitor_name)
    if "toggle" in args.dpms:
        monitor_name = args.dpms[-1].strip()
        focused_output = sock.get_focused_output()
        monitor_name = focused_output["name"]
        sock.dpms("toggle", monitor_name)


def view_list():
    views = sock.list_views()
    focused_view = sock.get_focused_view()
    focused_view_id = focused_view["id"]
    has_title = None
    if "has_title" in args.view:
        has_title = sub_arg.split("has_title ")[-1].strip()
    for view in views:
        # we do not need info about focused view
        # in case you need, just use the right wayctl call
        if view["id"] == focused_view_id:
            continue

        title = view["title"].lower()
        if has_title is not None:
            if has_title not in title:
                continue
        print("[{0}: {1}]".format(view["app-id"], view["title"]))
        view = json.dumps(view, indent=4)
        print(view)
        print("\n\n")


if args.view is not None:
    if "focused" in args.view:
        view_focused()
        sys.exit()

    if "list" in args.view:
        view_list()
        sys.exit()

if args.dpms is not None:
    dpms()

if args.screenshot is not None:
    if "focused" in args.screenshot:
        if "view" in args.screenshot:
            screenshot_view_focused()

    if "slurp" in args.screenshot:
        screenshot_slurp()

    if "focused" in args.screenshot:
        if "output" in args.screenshot:
            screenshot_focused_output()

    if "output" in args.screenshot:
        if "all" in args.screenshot:
            screenshot_all_outputs()

    if "view" in args.screenshot:
        if "all" in args.screenshot:
            screenshot_view_list()

if args.workspace is not None:
    if "set" in args.workspace:
        if "view" in args.workspace:
            if "focused" in args.workspace:
                wx = int(args.workspace[-1])
                wy = int(args.workspace[-2])
                ws = {"x": wx, "y": wy}
                focused_view_id = sock.get_focused_view_id()
                sock.set_workspace(ws, focused_view_id)

if args.session is not None:
    if "save" in args.session:
        save_views_session()

    if "start" in args.session:
        start_wayfire_session()

if args.resize is not None:
    if "views" in args.resize:
        if "left" in args.resize:
            resize_views_left()
        if "right" in args.resize:
            resize_views_right()
        if "up" in args.resize:
            resize_views_up()
        if "down" in args.resize:
            resize_views_down()


if args.switch is not None:
    if "views" in args.switch:
        switch_views_side()


if args.output is not None:
    if "view list" in args.output:
        output = sock.focused_output_views()
        pprint.pprint(output)

    if "focused" in args.output:
        output = sock.get_focused_output()
        output = json.dumps(output, indent=4)
        print(output)
