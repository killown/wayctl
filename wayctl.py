#!/usr/bin/env python3

import wayfire as ws
import os
import sys
import pprint
import json
import argparse
import shutil
from subprocess import call, check_output, Popen
from PIL import Image, ImageFont
import psutil
import threading
import time


class Wayctl:
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description="wayctl script utility for controlling some parts of the wayfire compositor through CLI or a script."
        )
        self.parser.add_argument(
            "--view",
            nargs="*",
            help="get info about views",
        )

        self.parser.add_argument(
            "--workspace",
            nargs="*",
            help="set the focused view to another workspace",
        )

        self.parser.add_argument(
            "--dpms",
            nargs="*",
            help="set dpms on/off/toggle",
        )

        self.parser.add_argument(
            "--output",
            nargs="*",
            help="get output info",
        )

        self.parser.add_argument(
            "--screenshot",
            nargs="*",
            help="options: (output, focused, slurp), output: screenshot the whole monitor, focused: screenshot the view, slurp: select a region to screenshot",
        )

        self.parser.add_argument(
            "--session",
            nargs="*",
            help="print session",
        )

        self.parser.add_argument(
            "--resize",
            nargs="*",
            help="resize views",
        )

        self.parser.add_argument(
            "--switch",
            nargs="*",
            help="switch views side",
        )

        self.args = self.parser.parse_args()

        self.addr = os.getenv("WAYFIRE_SOCKET")
        self.sock = ws.WayfireSocket(self.addr)

    def view_focused(self):
        view = self.sock.get_focused_view()
        print("[{0}: {1}]".format(view["app-id"], view["title"]))
        view_str = json.dumps(view, indent=4)
        print(view_str)
        print("\n\n")

    def create_new_session_file(self, file_path):
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

    def add_cmdline(self, view, process):
        ws_views = self.sock.get_workspaces_with_views()
        for view in self.sock.list_views():
            if process.pid == view["pid"]:
                view["cmdline"] = process.cmdline()
                for d in ws_views:
                    if d["view-id"] == view["id"]:
                        view["workspace"] = {"x": d["x"], "y": d["y"]}
                return view

    def save_views_session(self):
        list_views = self.sock.list_views()
        home = os.path.expanduser("~")
        wayfire = ".config/wayfire-session.json"
        save_path = os.path.join(home, wayfire)
        self.create_new_session_file(save_path)
        for view in list_views:
            view = self.add_cmdline(view, psutil.Process(view["pid"]))
            with open(save_path, "a") as f:
                json.dump(view, f, indent=4)
                f.write("\n--------view--------\n")

    def load_wayfire_session(self):
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

    def start_app(self, cmdline):
        return self.sock.run(" ".join(cmdline))["pid"]

    def start_wayfire_session(self):
        views = self.load_wayfire_session()
        for view in views:
            if "workspace" not in view:
                continue
            workspace = view["workspace"]
            self.sock.set_workspace(workspace)
            cmdline = view["cmdline"]
            pid = self.start_app(cmdline)
            time.sleep(1)

            # FIXME need a limit for that in case there is no pid at all
            while 1:
                if pid:
                    break
            view_id = None
            for v in self.sock.list_views():
                if v["pid"] == pid:
                    view_id = v["id"]
            if not view_id:
                continue

            self.sock.maximize(view_id)
            self.sock.set_workspace(workspace, view_id)
            self.sock.maximize(view_id)

    def screenshot_geometry(self):
        output = self.sock.get_focused_output()
        focused_view = self.sock.get_focused_view()
        ox = output["geometry"]["x"]
        oy = output["workarea"]["y"]
        vwidth = focused_view["geometry"]["width"]
        vheight = focused_view["geometry"]["height"]
        view_geometry = "{0},{1} {2}x{3}".format(ox, oy, vwidth, vheight)
        return view_geometry, focused_view

    def screenshot_view_focused(self):
        focused = self.sock.get_focused_view()
        view_id = focused["id"]
        app_id = focused["app-id"]
        filename = f"/tmp/{app_id}-{view_id}.png"
        self.screenshot_view_id(view_id, filename)
        self.sock.run(f"xdg-open {filename}")

    def screenshot_focused_output(self):
        self.sock.screenshot_focused_monitor()

    def run_slurp(self):
        return check_output(["slurp"]).decode().strip()

    def screenshot_slurp(self):
        slurp = self.run_slurp()
        focused = self.sock.get_focused_view()
        view_id = focused["id"]
        app_id = focused["app-id"]
        filename = f"/tmp/{app_id}-{view_id}.png"
        cmd = ["grim", "-g", f"{slurp}", filename]
        # must use call because Popen will not hang while creating the file thus xdg-open may fail
        call(cmd)
        Popen(["xdg-open", filename])

    def screenshot_slurp_focused_view(self):
        self.screenshot_view_focused()
        time.sleep(1)
        self.sock.fullscreen_focused()
        slurp = self.run_slurp()
        focused = self.sock.get_focused_view()
        view_id = focused["id"]
        app_id = focused["app-id"]
        filename = f"/tmp/{app_id}-{view_id}.png"
        cmd = ["grim", "-g", f"{slurp}", filename]
        call(cmd)
        Popen(["xdg-open", filename])

    def generate_screenshot_info(self, view_id, filename):
        font_size = 22
        font_filepath = "SourceCodePro-ExtraLight.otf"
        color = (80, 80, 80)
        view = self.sock.get_view(view_id)
        text = f"ID: {view['id']}, PID: {view['pid']}, Title: {view['title']}"
        font = ImageFont.truetype(font_filepath, size=font_size)
        mask_image = font.getmask(text, "L")
        size = mask_image.size[0] + 20, mask_image.size[1] + 20
        img = Image.new("RGBA", size)
        img.im.paste(color, (20, 20) + size, mask_image)
        img.save(filename)

    def screenshot_view_id(self, view_id, filename):
        self.sock.screenshot(view_id, filename)

    def screenshot_all_outputs(self):
        self.sock.screenshot_all_outputs()

    def create_directory(self, directory):
        if os.path.exists(directory):
            shutil.rmtree(directory)
        os.makedirs(directory)

    def screenshot_view_list(self):
        self.create_directory("/tmp/screenshots")
        for view in self.sock.list_views():
            view_id = view["id"]
            filename = str(view_id) + ".png"
            filename = os.path.join("/tmp/screenshots", filename)
            self.sock.screenshot(view_id, filename)
        Popen("xdg-open /tmp/screenshots".split())

    def resize_views_left(self):
        self.sock.resize_views_left()

    def resize_views_right(self):
        self.sock.resize_views_right()

    def resize_views_up(self):
        self.sock.resize_views_up()

    def resize_views_down(self):
        self.sock.resize_views_down()

    def switch_views_side(self):
        self.sock.switch_views_side()

    def dpms(self):
        if "on" in self.args.dpms:
            monitor_name = self.args.dpms[-1].strip()
            self.sock.dpms("on", monitor_name)
        if "off" in self.args.dpms:
            monitor_name = self.args.dpms[-1].strip()
            self.sock.dpms("off", monitor_name)
        if "toggle" in self.args.dpms:
            monitor_name = self.args.dpms[-1].strip()
            focused_output = self.sock.get_focused_output()
            monitor_name = focused_output["name"]
            self.sock.dpms("toggle", monitor_name)

    def view_list(self):
        views = self.sock.list_views()
        focused_view = self.sock.get_focused_view()
        focused_view_id = focused_view["id"]
        has_title = None
        if "has_title" in self.args.view:
            has_title = self.args.view.split("has_title ")[-1].strip()
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


# the cyclomatic complexity became to high, need a better way to deal with
if __name__ == "__main__":
    wayctl = Wayctl()

    if wayctl.args.view is not None:
        if "focused" in wayctl.args.view[0]:
            wayctl.view_focused()
            sys.exit()

        if "list" in wayctl.args.view[0]:
            wayctl.view_list()
            sys.exit()

    if wayctl.args.dpms is not None:
        wayctl.dpms()

    if wayctl.args.screenshot is not None:
        if "focused" in wayctl.args.screenshot[0]:
            if "view" in wayctl.args.screenshot[1]:
                wayctl.screenshot_view_focused()

        if "slurp" in wayctl.args.screenshot[0]:
            if len(wayctl.args.screenshot) == 1:
                wayctl.screenshot_slurp()
            if "focused" in wayctl.args.screenshot[0]:
                if "view" in wayctl.args.screenshot[1]:
                    wayctl.screenshot_slurp_focused_view()

        if "focused" in wayctl.args.screenshot[0]:
            if "output" in wayctl.args.screenshot[1]:
                wayctl.screenshot_focused_output()

        if "output" in wayctl.args.screenshot[0]:
            if "all" in wayctl.args.screenshot[1]:
                wayctl.screenshot_all_outputs()

        if "view" in wayctl.args.screenshot[0]:
            if "all" in wayctl.args.screenshot[1]:
                wayctl.screenshot_view_list()

    if wayctl.args.workspace is not None:
        if "set" in wayctl.args.workspace[0]:
            if "view" in wayctl.args.workspace[1]:
                if "focused" in wayctl.args.workspace[2]:
                    wx = int(wayctl.args.workspace[-1])
                    wy = int(wayctl.args.workspace[-2])
                    ws = {"x": wx, "y": wy}
                    focused_view_id = wayctl.sock.get_focused_view_id()
                    wayctl.sock.set_workspace(ws, focused_view_id)

    if wayctl.args.session is not None:
        if "save" in wayctl.args.session[0]:
            wayctl.save_views_session()

        if "start" in wayctl.args.session[0]:
            wayctl.start_wayfire_session()

    if wayctl.args.resize is not None:
        if "views" in wayctl.args.resize[0]:
            if "left" in wayctl.args.resize[1]:
                wayctl.resize_views_left()
            if "right" in wayctl.args.resize[1]:
                wayctl.resize_views_right()
            if "up" in wayctl.args.resize[1]:
                wayctl.resize_views_up()
            if "down" in wayctl.args.resize[1]:
                wayctl.resize_views_down()

    if wayctl.args.switch is not None:
        if "views" in wayctl.args.switch[0]:
            wayctl.switch_views_side()

    if wayctl.args.output is not None:
        if "view list" in wayctl.args.output[0]:
            output = wayctl.sock.focused_output_views()
            pprint.pprint(output)

        if "focused" in wayctl.args.output[0]:
            output = wayctl.sock.get_focused_output()
            output = json.dumps(output, indent=4)
            print(output)
