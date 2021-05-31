
# %%
from Environments.minigrid_labyrinth import Maze
import numpy as np
from Controllers.minigrid_controller import MiniGridController
from Controllers.meta_controller import MetaController
import pickle
import os, sys
from datetime import datetime
from MDP.high_level_mdp import HLMDP
from utils.results_saver import Results

# %% Setup and create the environment
env_settings = {
    'agent_start_states' : [(1,1,0)],
    'slip_p' : 0.1,
}

env = Maze(**env_settings)

prob_threshold = 0.95 # Desired probability of reaching the final goal
training_iters = 5e4
num_rollouts = 300
max_timesteps_per_component = 5e5

# %%
# load_folder_name = '2021-05-17_17-32-42_minigrid_labyrinth' # no slip prob labyrinth
# load_folder_name = '2021-05-17_17-58-27_minigrid_labyrinth' # no slip prob labyrinth
# load_folder_name = '2021-05-17_22-50-38_minigrid_labyrinth'
# save_learned_controllers = True
# train_controllers = False

load_folder_name = ''
save_learned_controllers = True
train_controllers = True

experiment_name = 'minigrid_labyrinth_baseline_one_component'

base_path = os.path.abspath(os.path.curdir)
string_ind = base_path.find('/src')
assert(string_ind >= 0)
base_path = base_path[0:string_ind + 4]
base_path = os.path.join(base_path, 'data', 'saved_controllers')

load_dir = os.path.join(base_path, load_folder_name)

if load_folder_name == '':
    now = datetime.now()
    dt_string = now.strftime("%Y-%m-%d_%H-%M-%S")
    save_path = os.path.join(base_path, dt_string + '_' + experiment_name)
else:
    save_path = os.path.join(base_path, load_folder_name)

if save_learned_controllers and not os.path.isdir(save_path):
    os.mkdir(save_path)

# %% Get the list of controllers
controller_list = []

if load_folder_name == '':

    # First room controllers
    initial_states = [(1,1,0)]
    final_states = env.goal_states
    controller_list.append(MiniGridController(0, initial_states, final_states, env_settings))

else:
    for controller_dir in os.listdir(load_dir):
        controller_load_path = os.path.join(load_dir, controller_dir)
        if os.path.isdir(controller_load_path):
            controller = MiniGridController(0, load_dir=controller_load_path)
            controller_list.append(controller)

    # re-order the controllers by index
    reordered_list = []
    for i in range(len(controller_list)):
        for controller in controller_list:
            if controller.controller_ind == i:
                reordered_list.append(controller)
    controller_list = reordered_list

# %% Create or load object to store the results
if load_folder_name == '':
    results = Results(controller_list, env_settings, prob_threshold, training_iters, num_rollouts)
else:
    results = Results(load_dir=load_dir)

# %%

# Initial training of the controllers
if train_controllers:
    total_timesteps = training_iters

    for controller_ind in range(len(controller_list)):

        print('Training controller {}'.format(controller_ind))
        controller = controller_list[controller_ind]
        # controller.learn(total_timesteps=total_timesteps)
        print('Completed training controller {}'.format(controller_ind))
        controller.eval_performance(n_episodes=num_rollouts)
        print('Controller {} achieved prob succes: {}'.format(controller_ind, controller.get_success_prob()))

        # Save learned controller
        if save_learned_controllers:
            controller_save_path = os.path.join(save_path, 'controller_{}'.format(controller_ind))
            controller.save(controller_save_path)

    results.update_training_steps(total_timesteps)
    results.update_controllers(controller_list)
    results.save(save_path)

# for controller in controller_list:
#     controller.demonstrate_capabilities(n_episodes=1, n_steps=20)

# %%

# Construct high-level MDP
hlmdp = HLMDP([(1,1,0)], env.goal_states, controller_list)
policy, reach_prob, feasible_flag = hlmdp.solve_max_reach_prob_policy()

meta_controller = MetaController(policy, hlmdp.controller_list, hlmdp.state_list)
meta_success_rate = meta_controller.eval_performance(env, n_episodes=num_rollouts, n_steps=200)

results.update_composition_data(meta_success_rate, num_rollouts, policy, reach_prob)
results.save(save_path)

# %%

total_timesteps = training_iters

while reach_prob < prob_threshold:
    optimistic_policy, required_reach_probs, optimistic_reach_prob, feasible_flag = hlmdp.solve_low_level_requirements(prob_threshold, max_timesteps_per_component=max_timesteps_per_component, action_independence=True)

    if not feasible_flag:
        print(required_reach_probs)

    for controller_ind in range(len(hlmdp.controller_list)):
        controller = hlmdp.controller_list[controller_ind]
        print('Init state: {}, Action: {}, End state: {}, Achieved success prob: {}, Required success prob: {}'.format(controller.get_init_states(), controller_ind, controller.get_final_states(), controller.get_success_prob(), controller.data['required_success_prob']))

    performance_gaps = []
    for controller_ind in range(len(hlmdp.controller_list)):
        controller = hlmdp.controller_list[controller_ind]
        performance_gaps.append(controller.data['required_success_prob'] - controller.get_success_prob())

    largest_gap_ind = np.argmax(performance_gaps)
    controller_to_train = hlmdp.controller_list[largest_gap_ind]

    print('Training controller {}'.format(largest_gap_ind))
    controller_to_train.learn(total_timesteps=total_timesteps)
    print('Completed training controller {}'.format(largest_gap_ind))
    controller_to_train.eval_performance(n_episodes=num_rollouts)

    # Save learned controller
    if save_learned_controllers:
        controller_save_path = os.path.join(save_path, 'controller_{}'.format(largest_gap_ind))
        if not os.path.isdir(controller_save_path):
            os.mkdir(controller_save_path)
        controller_to_train.save(controller_save_path)

    policy, reach_prob, feasible_flag = hlmdp.solve_max_reach_prob_policy()

    meta_controller = MetaController(policy, hlmdp.controller_list, hlmdp.state_list)
    meta_success_rate = meta_controller.eval_performance(env, n_episodes=num_rollouts, n_steps=200)

    results.update_training_steps(total_timesteps)
    results.update_controllers(hlmdp.controller_list)
    results.update_composition_data(meta_success_rate, num_rollouts, policy, reach_prob)
    results.save(save_path)

# %%
meta_controller = MetaController(policy, hlmdp.controller_list, hlmdp.state_list)

print('evaluating performance of meta controller')

meta_success_rate = meta_controller.eval_performance(env, n_episodes=num_rollouts, n_steps=200)
print('Predicted success prob: {}, empirically measured success prob: {}'.format(reach_prob, meta_success_rate))

n_episodes = 5
n_steps = 200
render = True
meta_controller.demonstrate_capabilities(env, n_episodes=n_episodes, n_steps=n_steps, render=render)

# %%