import gym
import numpy as np
from collections import deque
import torch
import wandb
import argparse

import random
from SAC.SAC import SAC
from DQN.DQN_Inps import DQN


# from DQN.DQN_Outs import DQN

def randString():
    import random
    random_string = ''
    for _ in range(5):
        # Considering only upper and lowercase letters
        random_integer = random.randint(97, 97 + 26 - 1)
        flip_bit = random.randint(0, 1)
        # Convert to lowercase if the flip bit is on
        random_integer = random_integer - 32 if flip_bit == 1 else random_integer
        # Keep appending random characters using chr(x)
        random_string += (chr(random_integer))
    return random_string


def get_config():
    parser = argparse.ArgumentParser(description='RL')
    parser.add_argument("--run_name", type=str, default="SAC", help="Run name, default: SAC")
    parser.add_argument("--env", type=str, default="CartPole-v1", help="Gym environment name, default: CartPole-v1")
    parser.add_argument("--episodes", type=int, default=10000, help="Number of episodes, default: 100")
    parser.add_argument("--buffer_size", type=int, default=100_000,
                        help="Maximal training dataset size, default: 100_000")
    parser.add_argument("--seed", type=int, default=1, help="Seed, default: 1")
    parser.add_argument("--log_video", type=int, default=0,
                        help="Log agent behaviour to wanbd when set to 1, default: 0")
    parser.add_argument("--save_every", type=int, default=100, help="Saves the network every x epochs, default: 25")
    parser.add_argument("--batch_size", type=int, default=256, help="Batch size, default: 256")

    args = parser.parse_args()
    return args


def train(config):
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    env = gym.make(config.env)

    env.seed(config.seed)
    env.action_space.seed(config.seed)

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    steps = 0
    total_steps = 0

    name = randString()
    wandb.init(project=f"Discrete Tester {config.env}", name=f'{name}-{randString()}')

    model = DQN(obs_dim=env.observation_space.shape[0],
                action_dim=env.action_space.n, learning_rate=1e-4, discount_factor=0.9, batch_size=32, )
    #
    # model = SAC(obs_dim=env.observation_space.shape[0],
    #             action_dim=env.action_space.n, learning_rate=3e-4, discount_factor=0.9)

    for i in range(1, config.episodes + 1):
        state = env.reset()
        episode_steps = 0
        rewards = 0
        while True:
            action = model.predict(state)
            steps += 1
            next_state, reward, done, _ = env.step(action)
            # env.render()
            model.learn_expirience(state, action, reward, next_state, done)
            model.train()
            state = next_state
            rewards += reward
            episode_steps += 1
            if done:
                break

        total_steps += episode_steps

        obj = {
                  "Reward": rewards
              }
        print(obj | model.get_log())
        print('---------------')
        wandb.log(obj | model.get_log())


if __name__ == "__main__":
    config = get_config()
    train(config)
