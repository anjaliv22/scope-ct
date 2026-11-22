import time
import numpy as np
import open3d as o3d
from tof_sim import render_range, add_tof_noise, range_to_depth, depth_to_points, make_scene
from sample_colon import build_colon

def make_target(mesh, voxel=1.0):
    pcd = o3d.geometry.PointCloud()
    pcd.points = mesh.vertices
    pcd.normals = mesh.vertex_normals
    return pcd.voxel_down_sample(voxel)

def make_source(pts_cam, voxel=1.0):
    pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts_cam))
    return pcd.voxel_down_sample(voxel)

def register(source, target, init_pose):
    """Coarse-to-fine point-to-plane ICP. Returns the estimated camera pose."""
    pose = init_pose
    for voxel, max_dist in [(2.0, 5.0), (1.0, 2.0)]: 
        src = source.voxel_down_sample(voxel)
        result = o3d.pipelines.registration.registration_icp(
            src, target, max_dist, pose,
            o3d.pipelines.registration.TransformationEstimationPointToPlane(),
            o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=30))
        pose = result.transformation
    return pose, result.fitness, result.inlier_rmse

def pose_error(est, true):
    t_err = np.linalg.norm(est[:3, 3] - true[:3, 3])
    R_err = est[:3, :3].T @ true[:3, :3]
    cos_angle = np.clip((np.trace(R_err) - 1) / 2, -1, 1)
    return t_err, np.degrees(np.arccos(cos_angle))


def track(scene, target, true_poses, init_pose, gen):
    est_poses, stats = [], []
    for k, true in enumerate(true_poses):
        #what the camera sees
        rng, cos_inc = render_range(scene, true)
        pts_cam = depth_to_points(range_to_depth(add_tof_noise(rng, cos_inc, gen)))
        source = make_source(pts_cam)

        # guess pose
        if k == 0:
            guess = init_pose
        elif k == 1:
            guess = est_poses[-1]
        else:
            prev, prev_prev = est_poses[-1], est_poses[-2]
            guess = prev @ np.linalg.inv(prev_prev) @ prev     # constant velocity

        t0 = time.perf_counter()
        est, fitness, rmse = register(source, target, guess)
        ms = (time.perf_counter() - t0) * 1000
        t_err, r_err = pose_error(est, true)
        lost = fitness < 0.8 or rmse > 1.5
        est_poses.append(est)
        stats.append([t_err, r_err, ms, fitness, rmse, lost])
        print(f"frame {k:3d}: {t_err:5.2f} mm  {r_err:5.2f} deg  {ms:4.0f} ms  {'LOST' if lost else ''}")

    return np.array(est_poses), np.array(stats)

if __name__ == "__main__":
    mesh, C, T, N1, N2, polyp_xyz = build_colon()
    scene = make_scene(mesh)
    target = make_target(mesh)
    true_poses = np.load("true_poses.npy")
    gen = np.random.default_rng(0)

    bump = np.eye(4)
    bump[:3, :3] = o3d.geometry.get_rotation_matrix_from_axis_angle(np.radians([2, -2, 1]))
    bump[:3, 3] = [2.0, -1.5, 1.5]
    init = true_poses[0] @ bump

    est_poses, stats = track(scene, target, true_poses, init, gen)
    np.save("est_poses.npy", est_poses)
    np.save("stats.npy", stats)

    t_err, r_err, ms = stats[:, 0], stats[:, 1], stats[:, 2]
    print("\n=== Summary ===")
    print(f"position error: mean {t_err.mean():.2f} mm, max {t_err.max():.2f} mm")
    print(f"rotation error: mean {r_err.mean():.2f} deg, max {r_err.max():.2f} deg")
    print(f"time per frame: mean {ms.mean():.0f} ms")
    print(f"lost frames:    {int(stats[:, 5].sum())} / {len(stats)}")