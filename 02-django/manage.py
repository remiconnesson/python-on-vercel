#!/usr/bin/env python
"""Django's command-line utility.

Vercel detects Django by finding this file (it must mention
DJANGO_SETTINGS_MODULE), then imports the settings to find WSGI_APPLICATION.
"""

import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
