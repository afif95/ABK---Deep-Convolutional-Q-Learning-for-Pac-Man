# -*- coding: utf-8 -*-
"""ABK - Deep Convolutional Q-Learning for Pac-Man

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/17QzWbu3NngD4dNuIfUt82Oag-C_yNToZ

# Deep Convolutional Q-Learning for Pac-Man

## Part 0 - Installing the required packages and importing the libraries

### Installing Gymnasium
"""

!pip install gymnasium
!pip install "gymnasium[atari, accept-rom-license]"
!apt-get install -y swig
!pip install gymnasium[box2d]

"""### Importing the libraries"""

import os
import random
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
from collections import deque
from torch.utils.data import DataLoader, TensorDataset

"""## Part 1 - Building the AI

### Creating the architecture of the Neural Network
"""

class Network(nn.Module):
  def __init__(self, action_size, seed=42):
    super(Network, self).__init__()
    self.seed = torch.manual_seed(seed)

    # convolutional layers: eyes of the AI

    self.conv1 = nn.Conv2d(3, 32, kernel_size = 8, stride = 4)
    self.bn1 = nn.BatchNorm2d(32)
    # convolution output size formula: (input size - kernel size + 2 * padding ) / stride + 1

    self.conv2 = nn.Conv2d(32, 64, kernel_size = 4, stride = 2)
    self.bn2 = nn.BatchNorm2d(64)
    # convolution output size formula: (input size - kernel size + 2 * padding ) / stride + 1

    self.conv3 = nn.Conv2d(64, 64, kernel_size = 3, stride = 1)
    self.bn3 = nn.BatchNorm2d(64)
    # convolution output size formula: (input size - kernel size + 2 * padding ) / stride + 1

    self.conv4 = nn.Conv2d(64, 128, kernel_size = 3, stride = 1)
    self.bn4 = nn.BatchNorm2d(128)

    # fully connected layers: brains of the AI

    # 10 * 10 * 128: shortcut without using formula
    self.fc1 = nn.Linear(10 * 10 * 128, 512)
    self.fc2 = nn.Linear(512, 256)
    self.fc3 = nn.Linear(256, action_size)

  def forward(self, state):
    x = F.relu(self.bn1(self.conv1(state)))
    x = F.relu(self.bn2(self.conv2(x)))
    x = F.relu(self.bn3(self.conv3(x)))
    x = F.relu(self.bn4(self.conv4(x)))
    # flattening: 1st dimension remains same, flatten 2nd dimension
    x = x.view(x.size(0), -1)
    x = F.relu(self.fc1(x))
    x = F.relu(self.fc2(x))
    return self.fc3(x)

"""## Part 2 - Training the AI

### Setting up the environment
"""

import gymnasium as gym
env = gym.make("MsPacmanDeterministic-v0", full_action_space = False)
# tuple
state_shape = env.observation_space.shape
state_size = env.observation_space.shape[0]
number_actions = env.action_space.n
print('State shape: ',state_shape)
print('State size: ', state_size)
print('Number of actions: ', number_actions)
print(env.observation_space)

"""### Initializing the hyperparameters"""

learning_rate = 5e-4
minibatch_size = 64
# gamma Ɣ
discount_factor = 0.99

"""### Preprocessing the frames"""

from PIL import Image
from torchvision import transforms

# real frames coming from pacman environment
def preprocess_frame(frame):
  # convert frame (numpy array) to PIL object
  frame = Image.fromarray(frame)
  # State shape: (210, 160, 3) isn't suitable for training DCQN, resize image to 128 x 128 and convert to pytorch tensor and normalize pixel values to 0/1
  preprocess = transforms.Compose([transforms.Resize((128,128)), transforms.ToTensor()])
  # unsqueeze(0): add 1 extra batch dimension to know which batch the state belongs to
  return preprocess(frame).unsqueeze(0)

"""### Implementing the Deep Convolutional Q Neural Network class"""

# defines the behaviour of the agent interacting with the space environment using DQN
class Agent():
  def __init__(self, action_size):
    self.device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu" )
    self.action_size = action_size
    # selects the actions, actively learns from the agent's experiences, weights are updated frequently
    self.local_qnetwork = Network(action_size).to(self.device)
    # calculates the target q values to be used in the training of the local q network
    self.target_qnetwork = Network(action_size).to(self.device)
    # self.local_qnetwork.parameters() are the weights of the network
    self.optimizer = optim.Adam(self.local_qnetwork.parameters(), lr = learning_rate)
    self.memory = deque(maxlen = 10000)

  def step(self, state, action, reward, next_state, done):
    # states are images coming in the form of a numpy array, then converted to pytorch tensor after normalization
    state = preprocess_frame(state)
    next_state = preprocess_frame(next_state)
    self.memory.append((state, action, reward, next_state, done))
    if len(self.memory) > minibatch_size:
      experiences = random.sample(self.memory, k = minibatch_size)
      self.learn(experiences, discount_factor)

  # helps agent to choose an action based on the current understanding of the optimal policy
  def act(self, state, epsilon = 0.):
    state = preprocess_frame(state).to(self.device)
    # evaluation mode
    self.local_qnetwork.eval()
    # disable gradient computation
    with torch.no_grad():
    # the forward method is implicitly called by being handled by PyTorch internally
      action_values = self.local_qnetwork(state)
    # set to training mode as opposed to prediction mode
    self.local_qnetwork.train()
    # Ɛ-greedy strategy
    if random.random() > epsilon:
      # choose the maximum value
      return np.argmax(action_values.cpu().data.numpy())
    else:
      # choose random value
      return random.choice(np.arange(self.action_size))

  # uses experiences sampled from ReplayMemory in order to update local q network's local q values towards the target q values
  def learn(self, experiences, discount_factor):
    # unzip experiences
    states, actions, rewards, next_states, dones = zip(*experiences)
    # torch.from_numpy converts to pytorch tensors to work on neural networks later
    # states, next_states are already pytorch tensors, vstack() function can take pytorch tensors as parameters and convert those into numpy arrays for stacking
    # from_numpy() reconverts the stacked numpy arrays into pytorch tensors
    # for the other variables, vstack() takes arrays as parameters
    # alternative is to use torch.cat()
    states = torch.from_numpy(np.vstack(states)).float().to(self.device)
    actions = torch.from_numpy(np.vstack(actions)).long().to(self.device)
    rewards = torch.from_numpy(np.vstack(rewards)).float().to(self.device)
    next_states = torch.from_numpy(np.vstack(next_states)).float().to(self.device)
    # np.uint8 is used to represent boolean values
    dones = torch.from_numpy(np.vstack(dones).astype(np.uint8)).float().to(self.device)
    # get maximum state q values from target q network, add batch dimension at position 1
    next_q_targets = self.target_qnetwork(next_states).detach().max(1)[0].unsqueeze(1)
    q_targets = rewards + (discount_factor * next_q_targets * (1-dones))
    q_expected = self.local_qnetwork(states).gather(1, actions)
    loss = F.mse_loss(q_expected,q_targets)
    # reset optimizer
    self.optimizer.zero_grad()
    loss.backward()
    # single optimization step to update model parameters (weights)
    self.optimizer.step()

"""### Initializing the Deep Convolutional Q Neural Network agent"""

agent = Agent(number_actions)

"""### Training the Deep Convolutional Q Neural Network agent"""

number_episodes = 2000
maximum_number_timesteps_per_episode = 10000
epsilon_starting_value = 1.0
epsilon_ending_value = 0.01
epsilon_decay_value = 0.995
epsilon = epsilon_starting_value
scores_on_100_episodes = deque(maxlen = 100)

for episode in range(1, number_episodes + 1):
  # reset the environment with initial state at the beginning
  state, _ = env.reset()
  # cummulative reward
  score = 0
  for t in range(maximum_number_timesteps_per_episode):
    action = agent.act(state, epsilon)
    next_state, reward, done, _ , _ = env.step(action)
    agent.step(state, action, reward, next_state, done)
    state = next_state
    score += reward
    if done:
      break
  scores_on_100_episodes.append(score)
  epsilon = max(epsilon_ending_value, epsilon_decay_value * epsilon)
  # /r carriage return with dynamic overriding effect: brings back the cursor to the start of the line in order to replace the previous print
  print('\rEpisode {}\tAverage Score: {:.2f}'.format(episode,np.mean(scores_on_100_episodes)),end="")
  if episode % 100 == 0:
    # without dynamic overriding effect
    print('\rEpisode {}\tAverage Score: {:.2f}'.format(episode,np.mean(scores_on_100_episodes)))
  if np.mean(scores_on_100_episodes) >= 500.0:
    # started winning after episode - 100 th episode
    print('\nEnvironment solved in {:d} episodes!\tAverage Score: {:.2f}'.format(episode - 100, np.mean(scores_on_100_episodes)))
    torch.save(agent.local_qnetwork.state_dict(),'checkpoint.pth')
    break

"""## Part 3 - Visualizing the results"""



import glob
import io
import base64
import imageio
from IPython.display import HTML, display
from gym.wrappers.monitoring.video_recorder import VideoRecorder

def show_video_of_model(agent, env_name):
    env = gym.make(env_name, render_mode='rgb_array')
    state, _ = env.reset()
    done = False
    frames = []
    while not done:
        frame = env.render()
        frames.append(frame)
        # no need to use agent.step() which includes learn() method as the model is not in training mode but in inference mode
        action = agent.act(state)
        state, reward, done, _, _ = env.step(action)
    env.close()
    imageio.mimsave('video.mp4', frames, fps=30)

show_video_of_model(agent, 'MsPacmanDeterministic-v0')

def show_video():
    mp4list = glob.glob('*.mp4')
    if len(mp4list) > 0:
        mp4 = mp4list[0]
        video = io.open(mp4, 'r+b').read()
        encoded = base64.b64encode(video)
        display(HTML(data='''<video alt="test" autoplay
                loop controls style="height: 400px;">
                <source src="data:video/mp4;base64,{0}" type="video/mp4" />
             </video>'''.format(encoded.decode('ascii'))))
    else:
        print("Could not find video")

show_video()