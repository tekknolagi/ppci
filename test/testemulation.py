import unittest
import os
import subprocess
import socket
import time
import shutil

from ppci.buildfunctions import construct

from ppci.target import target_list

# Store testdir for safe switch back to directory:
testdir = os.path.dirname(os.path.abspath(__file__))

def relpath(*args):
    return os.path.join(testdir, *args)

qemu_app = 'qemu-system-arm'


def tryrm(fn):
    try:
        os.remove(fn)
    except OSError:
        pass


def has_qemu():
    """ Determines if qemu is possible """
    if not hasattr(shutil, 'which'):
        return False
    return bool(shutil.which(qemu_app))


def runQemu(kernel, machine='lm3s811evb'):
    """ Runs qemu on a given kernel file """

    if not has_qemu():
        return ''
    # Check bin file exists:
    assert os.path.isfile(kernel)

    tryrm('qemucontrol.sock')
    tryrm('qemuserial.sock')

    # Listen to the control socket:
    qemu_control_serve = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    qemu_control_serve.bind('qemucontrol.sock')
    qemu_control_serve.listen(0)

    # Listen to the serial output:
    qemu_serial_serve = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    qemu_serial_serve.bind('qemuserial.sock')
    qemu_serial_serve.listen(0)

    args = [qemu_app, '-M', machine, '-m', '16M',
            '-nographic',
            '-kernel', kernel,
            '-monitor', 'unix:qemucontrol.sock',
            '-serial', 'unix:qemuserial.sock',
            '-S']
    p = subprocess.Popen(args)

    # qemu_serial Give process some time to boot:
    qemu_serial_serve.settimeout(3)
    qemu_control_serve.settimeout(3)
    qemu_serial, address_peer = qemu_serial_serve.accept()
    qemu_control, address_peer = qemu_control_serve.accept()

    # Give the go command:
    qemu_control.send('cont\n'.encode('ascii'))

    qemu_serial.settimeout(0.2)

    # Receive all data:
    data = bytearray()
    for i in range(400):
        try:
            data += qemu_serial.recv(1)
        except socket.timeout:
            break
    data = data.decode('ascii', errors='ignore')
    # print(data)

    # Send quit command:
    qemu_control.send("quit\n".encode('ascii'))
    if hasattr(subprocess, 'TimeoutExpired'):
        try:
            p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            p.kill()
    else:
        time.sleep(2)
        p.kill()
    qemu_control.close()
    qemu_serial.close()
    qemu_control_serve.close()
    qemu_serial_serve.close()

    tryrm('qemucontrol.sock')
    tryrm('qemuserial.sock')

    # Check that output was correct:
    return data


class EmulationTestCase(unittest.TestCase):
    """ Tests the compiler driver """

    def testM3Bare(self):
        """ Build bare m3 binary and emulate it """
        recipe = relpath('data', 'lm3s6965evb', 'build.xml')
        construct(recipe)
        if not has_qemu():
            self.skipTest('Not running Qemu test')
        data = runQemu('data/lm3s6965evb/bare.bin')
        self.assertEqual('Hello worle', data)

    def testA9Bare(self):
        """ Build vexpress cortex-A9 binary and emulate it """
        recipe = relpath('data', 'realview-pb-a8', 'build.xml')
        construct(recipe)
        if not has_qemu():
            self.skipTest('Not running Qemu test')
        data = runQemu('data/realview-pb-a8/hello.bin',
                       machine='vexpress-a9')
        self.assertEqual('Hello worle', data)

    def testBurn2(self):
        """ Compile the example for the stm32f4discovery board """
        recipe = relpath('data', 'stm32f4xx', 'build.xml')
        construct(recipe)


if __name__ == '__main__':
    unittest.main()
