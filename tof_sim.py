import  numpy as np 
import open3d as o3d
import matplotlib.pyplot as plt
from sample_colon import build_colon

# camera settings
WIDTH, HEIGHT = 160, 120 # img size
FOV = 90 

# focal length vals
fx = (WIDTH / 2) / np.tan(np.radians(FOV) / 2) 
fy = fx

cx, cy = WIDTH/2, HEIGHT/2 # img centre
MAX = 100

# direction of ray relative to the camera
def direction():
    u, v = np.meshgrid(np.arange(WIDTH), np.arange(HEIGHT))
    # u - cx => how left or right the slant is 
    # fx / fy => how far the camera is 
    dx = (u-cx)/fx
    dy = (v-cy)/fy
    return np.stack([dx, dy, np.ones_like(dx)], axis=-1)

def look_at(position, forward, up):
    z = forward / np.linalg.norm(forward)
    x = np.cross(z, up)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    pose = np.eye(4) # makes a grid with a diagonal of 1 
    pose[:3, 0] = x
    pose[:3, 1] = y
    pose[:3, 2] = z
    pose[:3, 3] = position
    return pose

def make_scene(mesh):
    scene = o3d.t.geometry.RaycastingScene()
    scene.add_triangles(o3d.t.geometry.TriangleMesh.from_legacy(mesh))
    return scene


def render_range(scene, pose):
    D = direction()
    D_unit = D / np.linalg.norm(D, axis=-1, keepdims=True)
    R, t = pose[:3, :3], pose[:3, 3]
    dirs_world = D_unit.reshape(-1, 3) @ R.T
    origins = np.repeat(t[None], len(dirs_world), axis=0)
    rays = np.hstack([origins, dirs_world]).astype(np.float32)

    hit = scene.cast_rays(o3d.core.Tensor(rays))
    rng = hit["t_hit"].numpy().reshape(HEIGHT, WIDTH)

    normals = hit["primitive_normals"].numpy().reshape(HEIGHT, WIDTH, 3)
    cos_inc = np.abs(np.sum(normals * dirs_world.reshape(HEIGHT, WIDTH, 3), axis=-1))

    rng[~np.isfinite(rng) | (rng > MAX)] = 0
    return rng, cos_inc

def range_to_depth(rng):
    D = direction()
    return rng / np.linalg.norm(D, axis=-1)

def depth_to_points(Z):
    D = direction()
    valid = Z > 0
    return D[valid] * Z[valid][:, None]

def add_tof_noise(rng, cos_inc, gen):
    # add a wee bit of noise for realistic purposes
    noisy = rng.copy()
    valid = rng > 0
    sigma = 0.05 + 0.0002 * rng ** 2
    noisy[valid] += gen.normal(0, sigma[valid])
    glare = cos_inc > 0.97

    grazing = cos_inc < 0.15
    dropout = gen.random(rng.shape) < 0.02

    noisy[glare | grazing | dropout] = 0
    return noisy

if __name__ == "__main__":
    # build a sample colon mesh tube
    mesh, C, T, N1, N2, polyp_xyz = build_colon()
    scene = make_scene(mesh)
    i = 5
    pose = look_at(C[i], T[i], N2[i]) # xyz pos / direction of flow / perp
    rng, cos_inc = render_range(scene, pose)
    noisy = add_tof_noise(rng, cos_inc, np.random.default_rng(0))
    Z = range_to_depth(noisy)

    #faking what hte sensor sees
    plt.imshow(Z, cmap="viridis")
    plt.colorbar(label="Z (mm)")
    plt.title("Simulated ToF depth map"); plt.show()

    #what are we looking at in the colon
    pts_cam = depth_to_points(Z)
    pts_world = pts_cam @ pose[:3, :3].T + pose[:3, 3]   # camera frame → world frame
    pcd = o3d.geometry.PointCloud(o3d.utility.Vector3dVector(pts_world))
    pcd.paint_uniform_color([1, 0, 0])
    o3d.visualization.draw_geometries([mesh, pcd], mesh_show_back_face=True)


