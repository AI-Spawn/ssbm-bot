import math
import time
from collections import deque

import colorama
import melee
import numpy as np

import GameManager
import MovesList
from CharacterController import CharacterController

from ModelCreator import create_model, Algorithm, train_every

import wandb


class Agent:
    def __init__(self, player_port: int, opponent_port: int, game: GameManager.Game, algorithm: Algorithm,
                 use_wandb: bool, log: bool = True):
        self.log = log
        self.use_wandb = use_wandb
        self.algorithm = algorithm
        self.game = game
        self.opponent_port = opponent_port
        self.player_port = player_port
        self.framedata = melee.FrameData()

        self.step = 0

        self.prev_gamestate = self.game.get_gamestate()
        obs = self.get_observation(self.prev_gamestate)
        num_inputs = len(obs)
        moves_list = MovesList.moves_list
        num_actions = len(moves_list)

        self.model = create_model(algorithm=algorithm, num_inputs=num_inputs, num_actions=num_actions)
        self.controller = CharacterController(player_port=self.player_port, game=self.game, moves_list=moves_list)
        self.action = 0

        self.kdr = deque(maxlen=20)
        self.rewards = deque(maxlen=4 * 60 * 60)

        self.action_tracker = deque(maxlen=3600)

        self.percent_at_death = deque(maxlen=1)
        self.percent_at_kill = deque(maxlen=1)
        self.percent_at_kill.append(300)
        self.percent_at_death.append(0)


        if use_wandb:
            wandb.init(project="SmashBot", name=f'{self.algorithm.name}-{int(time.time())}')
            print("wandb logged in")
        self.pi_a = 0.001

    def run_frame(self, gamestate: melee.GameState) -> None:
        died, already_dead = self.update_kdr(gamestate=gamestate, prev_gamestate=self.prev_gamestate)

        # Pass if a player is dead
        if already_dead:
            self.game.controller.release_all()
            self.prev_gamestate = gamestate
            return

        self.step += 1
        reward = self.get_reward(gamestate, self.prev_gamestate)

        move = MovesList.moves_list[self.action]
        if move.button is not None:
            reward -= 0.01
            print("Button")


        self.rewards.append(reward)

        prev_obs = self.get_observation(self.prev_gamestate)
        obs = self.get_observation(gamestate)
        if self.algorithm == Algorithm.PPO:
            self.model.learn_experience(obs=prev_obs, action=self.action, reward=reward, new_obs=obs, done=died,
                                        dead=died,
                                        pi_a=self.pi_a)
        else:
            self.model.learn_experience(prev_obs, self.action, reward, obs, False)

        te = train_every(self.algorithm)
        if self.step % te == 0 and te != -1:
            self.model.train()

        if self.step % (60*60)==0 and self.use_wandb:
            obj = {
                'Average Reward': np.mean(self.rewards),
                'Reward': reward,
                'KDR': np.sum(self.kdr),
                'Percent at Kill': np.mean(self.percent_at_kill),
                'Percent at Death': np.mean(self.percent_at_death),
                # '% Action 0': np.sum(self.action_tracker) / 3600
            }
            model_log = self.model.get_log()
            wandb.log(obj | model_log)
            if self.log:
                print(obj | model_log)


        if self.algorithm == Algorithm.PPO:
            self.action, self.pi_a = self.model.predict(obs)
        else:
            self.action = self.model.predict(obs)

        self.action_tracker.append(self.action)

        self.controller.act(self.action)
        self.prev_gamestate = gamestate

    def update_kdr(self, gamestate, prev_gamestate):
        new_player: melee.PlayerState = gamestate.players.get(self.player_port)
        new_opponent: melee.PlayerState = gamestate.players.get(self.opponent_port)
        old_player: melee.PlayerState = prev_gamestate.players.get(self.player_port)
        old_opponent: melee.PlayerState = prev_gamestate.players.get(self.opponent_port)

        someone_already_dead = False
        died = False
        if new_opponent.action in MovesList.dead_list:
            if old_opponent.action not in MovesList.dead_list:
                if self.log:
                    print(
                        f'{colorama.Fore.GREEN}{old_opponent.action} -> {new_opponent.action} @ {old_opponent.percent}%{colorama.Fore.RESET}')
                self.kdr.append(1)
                self.percent_at_kill.append(old_opponent.percent)
            else:
                someone_already_dead = True

        if new_player.action in MovesList.dead_list:
            if old_player.action not in MovesList.dead_list:
                if self.log:
                    print(
                        f'{colorama.Fore.RED}{old_player.action} -> {new_player.action} @ {old_player.percent}%{colorama.Fore.RESET}')
                self.kdr.append(-1)
                self.percent_at_death.append(old_player.percent)
                died = True
            else:
                someone_already_dead = True

        return died, someone_already_dead

    def get_player_obs(self, player: melee.PlayerState) -> list:
        x = player.position.x / 50
        y = player.position.y / 20
        percent = math.tanh(player.percent / 100)
        sheild = player.shield_strength / 60

        is_attacking = self.framedata.is_attack(player.character, player.action)
        on_ground = player.on_ground

        vel_y = (player.speed_y_self + player.speed_y_attack) / 10
        vel_x = (player.speed_x_attack + player.speed_air_x_self + player.speed_ground_x_self) / 10

        facing = 1 if player.facing else -1

        in_hitstun = 1 if player.hitlag_left else -1
        is_invounrable = 1 if player.invulnerable else -1

        special_fall = 1 if player.action in MovesList.special_fall_list else -1
        is_dead = 1 if player.action in MovesList.dead_list else -1

        jumps_left = player.jumps_left / self.framedata.max_jumps(player.character)

        attack_state = self.framedata.attack_state(player.character, player.action, player.action_frame)
        attack_active = 1 if attack_state == melee.AttackState.ATTACKING else -1
        attack_cooldown = 1 if attack_state == melee.AttackState.COOLDOWN else -1
        attack_windup = 1 if attack_state == melee.AttackState.WINDUP else -1

        is_bmove = 1 if self.framedata.is_bmove(player.character, player.action) else -1

        frames_left = self.framedata.frame_count(player.character,player.action)/20
        action_frame = player.action_frame/20


        return [special_fall, is_dead, vel_x, vel_y, x, y, percent, sheild, on_ground, is_attacking, facing,
                in_hitstun, is_invounrable, jumps_left, attack_windup, attack_active, attack_cooldown, is_bmove, frames_left, action_frame]

    def get_observation(self, gamestate: melee.GameState) -> np.ndarray:
        player: melee.PlayerState = gamestate.players.get(self.player_port)
        opponent: melee.PlayerState = gamestate.players.get(self.opponent_port)

        obs = []
        obs.append(self.get_player_obs(player))
        obs.append(self.get_player_obs(opponent))
        return np.array(obs).flatten()

    def get_reward(self, new_gamestate: melee.GameState, old_gamestate: melee.GameState) -> float:
        new_player: melee.PlayerState = new_gamestate.players.get(self.player_port)
        new_opponent: melee.PlayerState = new_gamestate.players.get(self.opponent_port)

        old_player: melee.PlayerState = old_gamestate.players.get(self.player_port)
        old_opponent: melee.PlayerState = old_gamestate.players.get(self.opponent_port)

        damage_dealt = max(new_opponent.percent - old_opponent.percent, 0)
        damage_received = max(new_player.percent - old_player.percent, 0)

        edge = melee.EDGE_POSITION.get(self.game.stage)
        bounds = 0
        if new_opponent.x > edge or new_opponent.x < -edge or new_opponent.y < 0:
            bounds += 0.2
        if new_player.x > edge or new_player.x < -edge or new_player.y < 0:
            bounds -= 0.3

        reward = math.tanh((damage_dealt - damage_received) / 4) * 0.7 + bounds

        if self.log:
            if damage_dealt > 0:
                print(f'{colorama.Fore.LIGHTGREEN_EX}Dealt {damage_dealt}%{colorama.Fore.RESET}')
            if damage_received > 0:
                print(f'{colorama.Fore.LIGHTMAGENTA_EX}Took {damage_received}%{colorama.Fore.RESET}')

        if new_player.action in MovesList.dead_list:
            reward = -1
        elif new_opponent.action in MovesList.dead_list:
            reward = 1

        # print(f'{self.action}: {reward}')

        return reward
