import gym
from stable_baselines3 import PPO

# Parallel environments
import gymEnv

import matplotlib.pyplot as plt


env = gymEnv.CharacterEnv()
# env = make_vec_env("CartPole-v1", n_envs=4)

model = PPO("MlpPolicy", env, verbose=1, learning_rate=0.005)
model.learn(total_timesteps=50000)

plt.plot(env.rewards)
plt.show()