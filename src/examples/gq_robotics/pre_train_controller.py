
# Run the labyrinth navigation experiment.
import os, sys
sys.path.append('../..')

from stable_baselines3.common.callbacks import CheckpointCallback

from environments.unity_env import build_unity_env
import numpy as np
from controllers.unity_labyrinth_controller import UnityLabyrinthController
import os, sys
from datetime import datetime

import torch
import random

# Setup and create the environment

env_settings = {
    'time_scale' : 99.0,
}

env, side_channels = build_unity_env()
side_channels['engine_config_channel'].set_configuration_parameters(
                                        time_scale=env_settings['time_scale'])

training_iters = 1e6

# Set the load directory (if loading pre-trained sub-systems) 
# or create a new directory in which to save results
load_folder_name = ''
save_learned_controllers = True

experiment_name = 'pretrain_warthog_controller'

base_path = os.path.abspath(os.path.curdir)
string_ind = base_path.find('src')
assert(string_ind >= 0)
base_path = base_path[0:string_ind + 4]
base_path = os.path.join(base_path, 'examples/gq_robotics', 'data', 'saved_controllers')

load_dir = os.path.join(base_path, load_folder_name)

if load_folder_name == '':
    now = datetime.now()
    dt_string = now.strftime("%Y-%m-%d_%H-%M-%S")
    rseed = int(now.time().strftime('%H%M%S'))
    save_path = os.path.join(base_path, dt_string + '_' + experiment_name)
else:
    save_path = os.path.join(base_path, load_folder_name)

if save_learned_controllers and not os.path.isdir(save_path):
    os.mkdir(save_path)

# Create the list of partially instantiated sub-systems
base_tensorboard_folder = './tensorboard/'

if load_folder_name == '':
    controller = UnityLabyrinthController(
        0,
        env,
        env_settings=env_settings,
        verbose=True,
        tensorboard_log=base_tensorboard_folder + 'pretrained_controller',
    )
else:
    controller_dir = 'pretrained_controller'
    controller_load_path = os.path.join(load_dir, controller_dir)
    controller = UnityLabyrinthController(
                0, 
                env, 
                load_dir=controller_load_path, 
                verbose=True
            )

rseed = int(now.time().strftime('%H%M%S'))

torch.manual_seed(rseed)
random.seed(rseed)
np.random.seed(rseed)

print('Random seed: {}'.format(rseed))

# Save learned controller
controller_save_path = \
    os.path.join(save_path, 'pretrained_controller')

# Save a checkpoint every 1000 steps
checkpoint_callback = CheckpointCallback(
    save_freq=1e4,
    save_path=controller_save_path,
    name_prefix="checkpoint",
    save_replay_buffer=False,
    save_vecnormalize=False,
)

# Train the sub-system and empirically evaluate its performance
print('Training controller')
controller.learn(
    side_channels['custom_side_channel'], 
    total_timesteps=training_iters,
    callback=checkpoint_callback
)
print('Completed training controller')

controller.save(controller_save_path)

env.close()