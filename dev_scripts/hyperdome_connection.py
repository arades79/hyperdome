# -*- coding: utf-8 -*-
"""
Hyperdome

Copyright (C) 2019 Skyelar Craver <scravers@protonmail.com>
                   and Steven Pitts <makusu2@gmail.com>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""
# Load onionshare module and resources from the source code tree
import os
import sys
import threading
import time
import traceback
import requests
import stem
# TODO there must be a cleaner way to do this
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.onionshare_dev_mode = True


from hyperdome_server import strings # noQA
from hyperdome_server.common import Common # noQA
from hyperdome_server.web import Web # noQA
from hyperdome_server.onion import Onion # noQA
from hyperdome_server.hyperdome_server import HyperdomeServer # noQA
from hyperdome_client.add_server_dialog import Server # noQA


class HyperdomeServerController:
    def __init__(self):
        self.onion = None
        self.app = None
        self.web = None
        self.exit_flag = False
        self.url = None
        self.t = None
        self.onion_connected = False

    def prepare_connection(self, num_tries: int = 10):
        for _ in range(num_tries):
            common = Common()
            common.load_settings()
            strings.load_strings(common)
            print(strings._('version_string').format(common.version))

            local_only = False
            common.debug = True
            shutdown_timeout = 0

            self.web = Web(common, False)

            self.onion = Onion(common)
            self.onion.connect(custom_settings=False,
                               config=False,
                               connect_timeout=120)
            # Start the onionshare app
            self.app = HyperdomeServer(common,
                                       self.onion,
                                       local_only,
                                       shutdown_timeout)
            self.app.choose_port()
            try:
                self.app.start_onion_service()
            except stem.Timeout:
                self.onion.cleanup()
                self.app.cleanup()
                self.web.stop(self.app.port)
                continue
            else:
                self.onion_connected = True
                break
        if not self.onion_connected:
            return False
        # Start OnionShare http service in new thread
        self.t = threading.Thread(target=self.web.start,
                                  args=(self.app.port, True),
                                  daemon=True)
        self.t.start()

        # TODO this looks dangerously like a race condition
        # Wait for web.generate_slug() to finish running
        time.sleep(0.2)

        # start shutdown timer thread
        if self.app.shutdown_timeout > 0:
            self.app.shutdown_timer.start()

        print('')
        self.url = 'http://{0:s}'.format(self.app.onion_host)
        print(strings._("give_this_url"))
        print(self.url)
        print()
        print(strings._("ctrlc_to_stop"))
        return True

    def run_server(self):
        successful_connection = self.prepare_connection()
        if not successful_connection:
            print("Failed to get a successful connection")
            return
        # Wait for app to close
        while self.t.is_alive():
            if self.exit_flag:
                print("Detected exit flag")
                return

            if self.app.shutdown_timeout > 0:
                # if the shutdown timer was set and has run out, stop the
                # server
                if not self.app.shutdown_timer.is_alive():
                    pass
                    # TODO if hyperdome session is over, break. Or just add
                    # to the conditions with app.shutdown_timer.is_alive().
            # Allow KeyboardInterrupt exception to be handled with threads
            # https://stackoverflow.com/questions/3788208
            time.sleep(0.2)

    def close(self):
        if self.app and self.web:
            self.web.stop(self.app.port)
        if self.onion:
            self.onion.cleanup()
        if self.app:
            self.app.cleanup()


class HyperdomeClientController:
    def __init__(self, onion_url):
        self.onion_url = onion_url
        self.common = None
        self.onion = None
        self.app = None
        self.server = None
        self._session = None
        self.uid = None
        self.therapist = None
        self.user = None
        self.success = None

    def close(self):
        if self.onion:
            self.onion.cleanup()
        if self.app:
            self.app.cleanup()

    def run_client(self):
        try:
            self.common = Common()
            self.common.define_css()
            self.common.load_settings()
            strings.load_strings(self.common)
            print(strings._('version_string').format(self.common.version))
            # signal.signal(signal.SIGINT, signal.SIG_DFL)
            self.common.debug = True
            self.onion = Onion(self.common)
            # I don't get why we're doing this
            self.app = HyperdomeServer(self.common, self.onion, False)
            self.server = Server(url=self.onion_url)
            # We might need more arguments to onion connect, unsure
            self.onion.connect(self.common.settings)
        except Exception as e:
            print(''.join(traceback.format_exception(type(e),
                                                     e,
                                                     e.__traceback__)))

    @property
    def session(self):
        """
        Lazy getter for tor proxy session.
        Ensures proxy isn't attempted until tor circuit established.
        """
        if self._session is None:
            self._session = requests.Session()
            if self.onion.is_authenticated():
                socks_address, socks_port = self.onion.get_tor_socks_port()
                self._session.proxies = {
                    'http': f'socks5h://{socks_address}:{socks_port}',
                    'https': f'socks5h://{socks_address}:{socks_port}'}
        return self._session


class HyperdomeTherapistController(HyperdomeClientController):
    def run_client_2(self):
        print("Running client 2 of therapist")
        self.server.username = "test"
        self.server.password = "test"
        self.session.post(f"{self.server.url}/therapist_signup",
                          data={"masterkey": "megumin",
                                "username": self.server.username,
                                "password": self.server.password})
        print("Signed up therapist")
        self.session.post(f"{self.server.url}/therapist_signin",
                          data={"username": self.server.username,
                                "password": self.server.password})
        print("Signed in therapist")
        self.session.post(f"{self.server.url}/message_from_therapist",
                          headers={"username": self.server.username,
                                   "password": self.server.password},
                          data={"message": "Therapist message 12345"})
        print("Posted therapist message")
        new_message = ''
        for _ in range(60):
            new_message = self.session.get(
                f"{self.server.url}/collect_therapist_messages",
                headers={"username": self.server.username,
                         "password": self.server.password}).text.strip()
            if new_message:
                break
            time.sleep(1)
        if new_message == "User message 12345":
            print("SUCCESS from therapist!")
            self.success = True
        else:
            print("ERROR from therapist: was expecting 'User message 12345', "
                  f"got '{new_message}'")
            self.success = False
        # time.sleep(5)


class HyperdomeUserController(HyperdomeClientController):
    def run_client_2(self):
        print("Running client 2 of user")
        self.uid = self.session.get(
            f'{self.server.url}/generate_guest_id').text
        print("User got uid")
        while not self.therapist:
            print("Waiting for connection to therapist...")
            self.therapist = self.session.post(
                f"{self.server.url}/request_therapist",
                data={"guest_id": self.uid}).text
        print("\n\n\n\n\nUser connected to therapist: ", self.therapist)
        self.session.post(f'{self.server.url}/message_from_user',
                          data={'message': "User message 12345",
                                'guest_id': self.uid})
        new_message = ''
        for _ in range(60):
            new_message = self.session.get(
                f"{self.server.url}/collect_guest_messages",
                data={"guest_id": self.uid}).text.strip()
            if new_message:
                break
            time.sleep(1)
        if new_message == "Therapist message 12345":
            print("SUCCESS from user!")
            self.success = True
        else:
            print("ERROR from user: was expecting 'Therapist message 12345', "
                  f"got '{new_message}'")
            self.success = False


def main():
    try:
        hsc = HyperdomeServerController()
        hsc_thread = threading.Thread(target=hsc.run_server, daemon=True)
        hsc_thread.start()
        while not hsc.onion:
            time.sleep(0.1)
        print("Onion created")
        while not hsc.onion.connected_to_tor:
            if not hsc_thread.is_alive():
                return "Server thread ended, returning"
            time.sleep(0.1)
        print("Connected to tor")
        while hsc_thread.is_alive() and not hsc.url:
            time.sleep(0.1)
        url_no_slug = hsc.url # slugs are no longer real
        print("\n\n\n\n\n\n\n\n\n\nGot HSC url")
        htc = HyperdomeTherapistController(url_no_slug)
        huc = HyperdomeUserController(url_no_slug)
        htc_thread = threading.Thread(target=htc.run_client, daemon=True)
        huc_thread = threading.Thread(target=huc.run_client, daemon=True)
        htc_thread.start()
        huc_thread.start()
        print("Started htc and huc threads")
        for _ in range(120):
            if not htc_thread.is_alive() and not huc_thread.is_alive():
                break
            time.sleep(1)
        if htc_thread.is_alive() or huc_thread.is_alive():
            return "Timed out while waiting for client communication"
        print("Client communications finished")
    except Exception as e:
        print(''.join(traceback.format_exception(type(e),
                                                 e,
                                                 e.__traceback__)))
    finally:
        for to_close in ('htc', 'huc', 'hsc'):
            if to_close in locals():
                locals()[to_close].close()
        # htc.close()
        # huc.close()
        # hsc.close()
        # print("Finished hsc cleanup")
        hsc.exit_flag = True
        print("Added exit flag")

    if htc.success and huc.success:
        return "Success"
    return f"htc.success: {htc.success}, huc.success: {huc.success}"


if __name__ == "__main__":
    result = main()
    print(f"\n\nResult: {result}")
