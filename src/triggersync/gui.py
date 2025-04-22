"""
Graphical User Interface for DSI-24 & QTM trigger synchronization.
"""

import argparse
import asyncio
from argparse import Namespace
import PySimpleGUI as sg
from triggersync.main import main as async_main


def run_gui():
    sg.theme('DarkBlue3')  # optional: set a modern theme
    layout = [
        [sg.Text('DSI-24 & QTM Trigger Sync', font=('Any', 16), justification='center', expand_x=True)],
        [sg.Text('Host', size=(15,1)), sg.InputText('127.0.0.1', key='host')],
        [sg.Text('Version', size=(15,1)), sg.InputText('1.22', key='version')],
        [sg.Text('Password', size=(15,1)), sg.InputText('', key='password', password_char='*')],
        [sg.Text('Duration (s)', size=(15,1)), sg.InputText('10.0', key='duration')],
        [sg.Text('Subject', size=(15,1)), sg.InputText('', key='subject')],
        [sg.Text('Task', size=(15,1)), sg.InputText('walking', key='task')],
        [sg.Text('BIDS Root', size=(15,1)), sg.InputText('', key='bids_root'), sg.FolderBrowse(button_text='Browse')],
        [sg.Checkbox('Enable Parallel Triggers', default=False, key='triggers', expand_x=True)],
        [sg.Text('Address (hex)', size=(15,1)), sg.InputText('0x4000', key='address')],
        [sg.Text('Pulse (ms)', size=(15,1)), sg.InputText('5.0', key='pulse')],
        [sg.Text('Start Code', size=(15,1)), sg.InputText('1', key='start_code')],
        [sg.Text('End Code', size=(15,1)), sg.InputText('2', key='end_code')],
        [sg.Button('Start', size=(10,1)), sg.Button('Cancel', size=(10,1))]
    ]

    window = sg.Window('Trigger Sync Setup', layout, finalize=True)
    while True:
        event, values = window.read()
        if event in (sg.WIN_CLOSED, 'Cancel'):
            break
        if event == 'Start':
            # build args
            args = Namespace(
                host=values['host'], version=values['version'], password=values['password'],
                duration=float(values['duration']), subject=values['subject'], task=values['task'],
                bids_root=values['bids_root'], triggers=values['triggers'], address=values['address'],
                pulse=float(values['pulse']), start_code=int(values['start_code']), end_code=int(values['end_code'])
            )
            window.close()
            # run async main
            asyncio.run(async_main(args))
            break
    window.close()


if __name__ == '__main__':
    run_gui()