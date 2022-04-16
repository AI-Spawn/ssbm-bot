import Args
import GameManager
import melee
import platform

import os
import DataHandler
import numpy as np

from encoder import decode_from_number

args = Args.get_args()

if __name__ == '__main__':
    character = melee.Character.CPTFALCON
    opponent = melee.Character.CPTFALCON if not args.compete else character
    stage = melee.Stage.FINAL_DESTINATION

    tree, map = DataHandler.load_model(player_character=character, opponent_character=opponent, stage=stage)

    game = GameManager.Game(args)
    game.enterMatch(cpu_level=9, opponant_character=opponent,
                    player_character=character,
                    stage=stage, rules=False)

    num_buttons = len(DataHandler.buttons) + 1
    axis_size = 3
    num_c = 5
    maxes = [axis_size, axis_size, num_c, num_buttons]


    while True:
        gamestate = game.get_gamestate()

        action = DataHandler.predict(tree=tree, map=map, gamestate=gamestate, player_port=game.controller.port,
                                     opponent_port=game.controller_opponent.port)
        move_x, move_y, c, button = decode_from_number(action, maxes)
        print(action)
        # print(button)
        # print(move_x)
        # print(move_y)
        # print(c)
        # print(out)
        print('----------')
        # print(trainer.buttons)
        if button > 0:
            game.controller.press_button(DataHandler.buttons[button - 1][0])

        if c == 0:
            game.controller.tilt_analog(melee.Button.BUTTON_C, 0.5, 0.5)
        else:
            if c == 1:
                game.controller.tilt_analog(melee.Button.BUTTON_C, 0, 0.5)
            elif c == 2:
                game.controller.tilt_analog(melee.Button.BUTTON_C, 1, 0.5)
            elif c == 3:
                game.controller.tilt_analog(melee.Button.BUTTON_C, 0.5, 0)
            elif c == 4:
                game.controller.tilt_analog(melee.Button.BUTTON_C, 0.5, 1)
            for i in range(5):
                gamestate = game.get_gamestate()

        game.controller.tilt_analog(melee.Button.BUTTON_MAIN, move_x / 2, move_y / 2)
        gamestate = game.get_gamestate()
        for b in DataHandler.buttons:
            game.controller.release_button(b[0])
        game.controller.tilt_analog(melee.Button.BUTTON_C, 0.5, 0.5)

        # game.controller.release_all()
