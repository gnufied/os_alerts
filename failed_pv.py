#!/usr/bin/env python

import subprocess
import json
import datetime
import time
import re

class PV(object):
    def __init__(self, pv_name):
        self.pv_name = pv_name


class FailePV(object):
    def run(self):
        print "Running this"

    def get_failed_pv(self):
        output = subprocess.check_output(['oc', 'get', 'pv', '-o', 'json'])
        pv_json = json.loads(output)
        pv_items = pv_json['items']

if __name__ == "__main__":
    a = FailePV()
    a.run()
