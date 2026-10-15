from lcd1602 import *
from yolo_uno import *

lcd1602 = LCD1602()

async def setup():

  print('App started')
  lcd1602.show(str('Hello'), 1 - 1, 1 - 1)
  lcd1602.show(str('OhStem Education'), 2 - 1, 1 - 1)

async def main():
  await setup()
  while True:
    await asleep_ms(100)

run_loop(main())
