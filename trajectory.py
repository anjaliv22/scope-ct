import numpy as np 
import open3d as o3d
from tof_sim import look_at
from sample_colon import build_colon

def make_traj(C, T, n1, n2, start=50, end=550, step=2):
    poses = []
    for k, i in enumerate(range(start, end, step)):
        # add sideways and up and down drift
        a = 3.0 * np.sin(0.05 * k)                      
        b = 2.0 * np.cos(0.07 * k)
        position = C[i] + a * n1[i] + b * n2[i]

        # tilt the camera  little 
        forward = T[i] + 0.10 * np.sin(0.04 * k) * n1[i] + 0.08 * np.cos(0.03 * k) * n2[i]

        # twist the camera
        roll = 0.5 * np.sin(0.02 * k)                  
        up = np.cos(roll) * n2[i] + np.sin(roll) * n1[i]
        poses.append(look_at(position, forward, up))

    return poses

if __name__ == "__main__":
    mesh, C, T, N1, N2, polyp_xyz = build_colon()
    poses = make_traj(C, T, N1, N2)
    print("Frames: ", len(poses))
    steps = [np.linalg.norm(poses[k+1][:3, 3] - poses[k][:3, 3]) for k in range(len(poses) - 1)]
    print("avg step (mm):", np.mean(steps))          
    frames = [o3d.geometry.TriangleMesh.create_coordinate_frame(size=6).transform(p)
              for p in poses[::10]]
    mesh.paint_uniform_color([0.8, 0.8, 0.8])
    o3d.visualization.draw_geometries([mesh, *frames], mesh_show_back_face=True)

    np.save("true_poses.npy", np.array(poses)) 


