import os
import json
import rospy
import torch
import argparse
import numpy as np
from torch.utils.tensorboard import SummaryWriter
from env import Env
from agent import TD3
from utils.replay_buffer import ReplayBuffer

if __name__ == "__main__":
    rospy.init_node("test_node")
    parser = argparse.ArgumentParser()
    ###################   Environment Argument   ###################
    parser.add_argument("--episode_num", default=10000, type=int, help="Specify total training episodes")
    parser.add_argument("--max_timesteps", default=100000, type=int, help="Sepcify max timesteps for each episode")
    ###################   Policy Argument   ###################
    parser.add_argument("--policy", default="TD3", type=str, choices=["TD3", "NFWPO"], help="Choose a policy to interact with environment")
    parser.add_argument("--noise_scale", default=0.2, type=float, help="The scale of Gaussian noise")
    parser.add_argument("--max_noise", default=0.5, type=float, help="Maximum ratio value of noise to max action")
    parser.add_argument("--discount", default=0.99, type=float, help="Discount factor (gamma)")
    parser.add_argument("--update_freq", default=2, type=int, help="Delayed policy update frequency")
    parser.add_argument("--tau", default=0.005, type=float, help="Target network update rate (soft update)")
    ###################   Training Argument   ###################
    parser.add_argument("--name", default="", type=str, help="The name of the simulation")
    parser.add_argument("--seed", type=int, help="Set random seed")
    parser.add_argument("--load_model", default="", type=str, help="Load a pretrained model")
    parser.add_argument("--save_buffer", action="store_true", help="Save the replay buffer or not")
    parser.add_argument("--load_buffer", default="", type=str, help="Load a replay buffer")
    args = parser.parse_args()

    # select environment
    env = Env()
    state_dim = env.observation_space.shape[0]
    action_dim = env.action_space.shape[0]
    max_action = min(env.action_space.high)
    min_action = max(env.action_space.low)

    # select agent
    kwargs = {"noise_scale": args.noise_scale,
              "max_noise": args.max_noise,
              "action_high": max_action,
              "action_low": min_action,
              "discount": args.discount,
              "update_freq": args.update_freq,
              "tau": args.tau}
    if args.policy == "TD3":
        agent = TD3(state_dim, action_dim, max_action, **kwargs)
    else:
        exit(f"[Error] \033[91mPolicy {args.policy} not supported\033[0m")

    if args.load_model != "":
        agent.load_model(args.load_model)
    else:
        exit(f"[Error] \033[91mNo model loaded\033[0m")

    # create replay buffer
    replay_buffer = ReplayBuffer(state_dim, action_dim)

    if args.load_buffer != "":
        replay_buffer.load(args.load_buffer)

    # Set random seeds
    if args.seed != None:
        env.seed(args.seed)
        env.action_space.seed(args.seed)
        torch.manual_seed(args.seed)
        np.random.seed(args.seed)

    # record simulation data
    if not os.path.exists("./simulation/test"):
        os.makedirs("./simulation/test")

    if args.name == "":
        simulation_name = f"{args.policy}"
    else:
        simulation_name = args.name

    save_path = f"./simulation/test/{simulation_name}"
    if os.path.exists(save_path):
        save_path_serial = 1
        while os.path.exists(f"{save_path}_{save_path_serial}"):
            save_path_serial += 1
        save_path += f"_{save_path_serial}"
        os.makedirs(save_path)

    if not os.path.exists(save_path + "/logs"):
        os.makedirs(save_path + "/logs")

    with open(save_path + "/args_records.txt", "w") as f:
        args_dict = vars(args)
        json.dump({"args": args_dict}, sort_keys=True, indent=4, fp=f)

    writer = SummaryWriter(save_path + "/logs")

    # start training
    try:
        global_steps = 0
        for ep in range(args.episode_num):
            print(f"Episode: {ep+1}")
            episode_reward = 0.0
            state = env.reset()

            for t in range(args.max_timesteps):
                action = (agent.select_action(state)).clip(min_action, max_action)

                next_state, reward, done, _ = env.step(action)
                episode_reward += reward

                replay_buffer.add(state, action, reward, next_state, done)
                writer.add_scalar("Action/Velocity_X", action[0], global_steps+1)
                writer.add_scalar("Action/Velocity_Y", action[1], global_steps+1)
                writer.add_scalar("Action/Velocity_Z", action[2], global_steps+1)
                global_steps += 1

                if done:
                    break
                state = next_state

            print(f"[INFO] Episode Reward: {episode_reward}, Data: {replay_buffer.size}")
            writer.add_scalar("Reward/Episode_Reward", episode_reward, ep+1)

            print()

    except Exception as e:
        print("\033[93m" + str(e) + "\033[0m")

    finally:
        if args.save_buffer:
            replay_buffer.save(save_path + "/replay_buffer.npz")
