import time
import numpy as np
import open3d as o3d
from sample_colon import build_colon
from tof_sim import make_scene, render_range, add_tof_noise, range_to_depth, depth_to_points

def update_line(ls, points, color):
    pts = np.asarray(points)
    ls.points = o3d.utility.Vector3dVector(pts)
    ls.lines = o3d.utility.Vector2iVector([[i, i + 1] for i in range(len(pts) - 1)])
    ls.paint_uniform_color(color)


def nearest_polyp_ahead(pose, polyp_xyz):
    R, t = pose[:3, :3], pose[:3, 3]
    p_cam = (polyp_xyz - t) @ R  
    ahead = p_cam[:, 2] > 0          
    if not ahead.any():
        return None, None
    d = np.linalg.norm(p_cam, axis=1)
    d[~ahead] = np.inf
    j = int(np.argmin(d))
    return j + 1, d[j]


if __name__ == "__main__":
    mesh, C, T, N1, N2, polyp_xyz = build_colon()
    scene = make_scene(mesh)
    true_poses = np.load("true_poses.npy")
    est_poses = np.load("est_poses.npy")
    gen = np.random.default_rng(0)
    BLUE, ORANGE, GREEN = [0.2, 0.4, 1.0], [1.0, 0.5, 0.0], [0.1, 0.8, 0.3]

    colon = mesh.sample_points_uniformly(40000)
    colon.paint_uniform_color([0.75, 0.75, 0.75])
    polyps = []
    for p in polyp_xyz:
        s = o3d.geometry.TriangleMesh.create_sphere(radius=2.5).translate(p)
        s.paint_uniform_color([1, 0, 0])
        polyps.append(s)

    patch = o3d.geometry.PointCloud()
    true_line, est_line = o3d.geometry.LineSet(), o3d.geometry.LineSet()
    update_line(true_line, true_poses[:2, :3, 3], BLUE)
    update_line(est_line, est_poses[:2, :3, 3], ORANGE)
    cam = o3d.geometry.TriangleMesh.create_coordinate_frame(size=8)
    cam_base = np.asarray(cam.vertices).copy()     

    vis = o3d.visualization.Visualizer()
    vis.create_window("Scope tracking (ICP vs ground truth)", 1280, 800)
    for g in [colon, *polyps, patch, true_line, est_line, cam]:
        vis.add_geometry(g)
    vis.get_render_option().point_size = 2

    for k in range(len(est_poses)):
        est = est_poses[k]

        rng, cos_inc = render_range(scene, true_poses[k])
        pts_cam = depth_to_points(range_to_depth(add_tof_noise(rng, cos_inc, gen)))
        patch.points = o3d.utility.Vector3dVector(pts_cam @ est[:3, :3].T + est[:3, 3])
        patch.paint_uniform_color(GREEN)
        n = max(k + 1, 2)
        update_line(true_line, true_poses[:n, :3, 3], BLUE)
        update_line(est_line, est_poses[:n, :3, 3], ORANGE)
        cam.vertices = o3d.utility.Vector3dVector(cam_base @ est[:3, :3].T + est[:3, 3])

        j, d = nearest_polyp_ahead(est, polyp_xyz)
        print(f"frame {k:3d}  |  " + (f"polyp {j}: {d:5.1f} mm ahead" if j else "no polyp ahead"))

        for g in [patch, true_line, est_line, cam]:
            vis.update_geometry(g)
        if not vis.poll_events():         
            break
        vis.update_renderer()
        time.sleep(1 / 20)                

    vis.run()                              
    vis.destroy_window()
