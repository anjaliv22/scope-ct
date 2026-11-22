import numpy as np
import open3d as o3d
from sample_colon import build_colon
from tof_sim import make_scene, render_range, add_tof_noise, range_to_depth, depth_to_points
from tracker import make_target, make_source, register, pose_error
from viewer import update_line, nearest_polyp_ahead

STEP_MM = 2.0      # how far one forward/back press moves the scope
TURN_DEG = 3.0     # how far one turn/tilt/roll press rotates it
JOLT_MM = 8.0      # size of the sudden jump used to break tracking on purpose

GREY, BLUE, ORANGE = [0.75, 0.75, 0.75], [0.2, 0.4, 1.0], [1.0, 0.5, 0.0]
GREEN, RED = [0.1, 0.8, 0.3], [1.0, 0.1, 0.1]


def rotate(axis, deg):
    M = np.eye(4)
    M[:3, :3] = o3d.geometry.get_rotation_matrix_from_axis_angle(
        np.radians(deg) * np.asarray(axis, dtype=float))
    return M


def translate(x, y, z):
    M = np.eye(4)
    M[:3, 3] = [x, y, z]
    return M


class Driver:
    def __init__(self):
        mesh, C, T, N1, N2, self.polyp_xyz = build_colon()
        self.scene = make_scene(mesh)
        self.target = make_target(mesh)
        self.gen = np.random.default_rng(0)

        start = np.load("true_poses.npy")[0]
        self.true = start.copy()          # where the scope really is (you control this)
        self.est = start.copy()           # where ICP thinks it is
        self.true_path = [start[:3, 3]]
        self.est_path = [start[:3, 3]]

        # Geometry
        self.colon = mesh.sample_points_uniformly(40000)
        self.colon.paint_uniform_color(GREY)
        self.polyps = []
        for p in self.polyp_xyz:
            s = o3d.geometry.TriangleMesh.create_sphere(radius=2.5).translate(p)
            s.paint_uniform_color([1, 0, 0])
            self.polyps.append(s)
        self.patch = o3d.geometry.PointCloud()
        self.true_line = o3d.geometry.LineSet()
        self.est_line = o3d.geometry.LineSet()
        self.cam = o3d.geometry.TriangleMesh.create_coordinate_frame(size=8)
        self.cam_base = np.asarray(self.cam.vertices).copy()

    def step(self, vis=None):
        rng, cos_inc = render_range(self.scene, self.true)
        pts_cam = depth_to_points(range_to_depth(add_tof_noise(rng, cos_inc, self.gen)))
        if len(pts_cam) < 500:
            print("Too few points — did the scope leave the colon? Press Z to reset.")
            return

        # Live ICP, starting from the last estimate
        self.est, fitness, rmse = register(make_source(pts_cam), self.target, self.est)
        t_err, r_err = pose_error(self.est, self.true)
        lost = fitness < 0.8 or rmse > 1.5

        # Update the drawing
        R, t = self.est[:3, :3], self.est[:3, 3]
        self.patch.points = o3d.utility.Vector3dVector(pts_cam @ R.T + t)
        self.patch.paint_uniform_color(RED if lost else GREEN)
        self.true_path.append(self.true[:3, 3])
        self.est_path.append(t)
        update_line(self.true_line, self.true_path, BLUE)
        update_line(self.est_line, self.est_path, ORANGE)
        self.cam.vertices = o3d.utility.Vector3dVector(self.cam_base @ R.T + t)

        # Status line
        j, d = nearest_polyp_ahead(self.est, self.polyp_xyz)
        polyp = f"polyp {j}: {d:5.1f} mm ahead" if j else "no polyp ahead"
        status = "LOST" if lost else "ok"
        print(f"error {t_err:5.2f} mm {r_err:5.2f} deg | fitness {fitness:.2f} "
              f"rmse {rmse:.2f} | {status:4s} | {polyp}")

        if vis is not None:
            for g in [self.patch, self.true_line, self.est_line, self.cam]:
                vis.update_geometry(g)

    def key(self, delta):
        def handler(vis):
            self.true = self.true @ delta
            self.step(vis)
            return True
        return handler

    def jolt(self, vis):
        self.true = self.true @ translate(JOLT_MM * 0.6, -JOLT_MM * 0.4, JOLT_MM * 0.7)
        print(">>> JOLT: scope jumped suddenly")
        self.step(vis)
        return True

    def reset(self, vis):
        self.est = self.true.copy()
        print(">>> RESET: tracker re-initialized")
        self.step(vis)
        return True


if __name__ == "__main__":
    d = Driver()
    d.step()                                      

    vis = o3d.visualization.VisualizerWithKeyCallback()
    vis.create_window("Drive the scope (live ICP)", 1280, 800)
    for g in [d.colon, *d.polyps, d.patch, d.true_line, d.est_line, d.cam]:
        vis.add_geometry(g)
    vis.get_render_option().point_size = 2

    UP, DOWN, LEFT, RIGHT = 265, 264, 263, 262     # arrow key codes
    vis.register_key_callback(UP,       d.key(translate(0, 0,  STEP_MM)))   # forward
    vis.register_key_callback(DOWN,     d.key(translate(0, 0, -STEP_MM)))   # back
    vis.register_key_callback(LEFT,     d.key(rotate([0, 1, 0], -TURN_DEG)))  # turn left
    vis.register_key_callback(RIGHT,    d.key(rotate([0, 1, 0],  TURN_DEG)))  # turn right
    vis.register_key_callback(ord("I"), d.key(rotate([1, 0, 0],  TURN_DEG)))  # tilt up
    vis.register_key_callback(ord("K"), d.key(rotate([1, 0, 0], -TURN_DEG)))  # tilt down
    vis.register_key_callback(ord("U"), d.key(rotate([0, 0, 1], -TURN_DEG)))  # roll left
    vis.register_key_callback(ord("O"), d.key(rotate([0, 0, 1],  TURN_DEG)))  # roll right
    vis.register_key_callback(ord("X"), d.jolt)                                # break tracking
    vis.register_key_callback(ord("Z"), d.reset)                               # recover

    print("""
Controls (click the 3D window first):
  Up / Down      push forward / pull back
  Left / Right   turn left / right
  I / K          tilt up / down
  U / O          roll left / right
  X              jolt (sudden jump → watch tracking fail)
  Z              reset tracker (re-localize)
  Esc            quit
""")
    vis.run()
    vis.destroy_window()