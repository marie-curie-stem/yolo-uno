""" 
Blink LED demo: 
toggles the built-in LED on and off repeatedly to demonstrate basic GPIO control.
"""

from pins import *
from yolo_uno import *

LED = Pins(D13_PIN)

async def setup():

  print('App started')
  for count in range(10):
    LED.write_digital(1)
    await asleep_ms(1000)
    LED.write_digital(0)
    await asleep_ms(1000)

async def main():
  await setup()
  while True:
    await asleep_ms(100)

run_loop(main())
