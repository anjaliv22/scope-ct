# build a mesh tube to simulate a patients ct scans for testing

import numpy as np 
import open3d as o3d
import matplotlib.pyplot as plt

#mesh resolution 
NUM_RINGS = 600
NUM_AROUND = 96

#in mm (sample colon dimensions)
LENGTH = 300.0 
RADIUS = 20.0

# path the colon follows -> the lumen 
def make_centerline(n=NUM_RINGS, length=LENGTH):
    t = np.linspace(0, 1, n)
    x = length * t 
    y = 40 * np.sin(2*np.pi*1.1*t) 
    z = 25 * np.sin(2 * np.pi * 0.7 * t + 0.5) 
    return np.stack([x, y, z], axis=1) # an array of points x,y,z

def make_frames(C):
    T = np.gradient(C, axis=0)
    # array saying the direction of tube from that point
    T = T / np.linalg.norm(T, axis=1, keepdims=True)

    # make arrow perpendicular to T
    up = np.array([0.0, 0.0, 1.0])
    N1 = np.cross(T, up)
    N1 = N1 / np.linalg.norm(N1, axis=1, keepdims=True)
    #another one
    N2 = np.cross(T, N1) # line perp to T and N1 
    return T, N1, N2

def make_rings(C, n1, n2, r, theta):
    P = np.zeros((len(C), len(theta), 3))
    for i in range(len(C)):
        for j in range(len(theta)):
            direction = np.cos(theta[j]) * N1[i] + np.sin(theta[j]) * N2[i]
            P[i, j] = C[i] + r[i, j] * direction  
    return P

def idx(i, j, n=NUM_AROUND):
        return i * n + (j % n)

def make_mesh(P):
    n_rings, n_around, _ = P.shape
    vertices = P.reshape(-1, 3) 

    triangles = []
    for i in range(n_rings - 1):
        for j in range(n_around):
            a = idx(i, j) 
            b = idx(i, j + 1) 
            c = idx(i + 1, j) 
            d = idx(i + 1, j + 1)
            triangles.append([a, b, c])
            triangles.append([c, b, d])

    mesh = o3d.geometry.TriangleMesh()
    mesh.vertices = o3d.utility.Vector3dVector(vertices)
    mesh.triangles = o3d.utility.Vector3iVector(np.array(triangles))
    mesh.compute_vertex_normals()     
    return mesh

def make_radius(s, theta, seed=7):
    rng = np.random.default_rng(seed)
    S, TH = np.meshgrid(s, theta, indexing="ij")
    r = np.full(S.shape, RADIUS)
    r *= 1 + 0.15 * np.cos(2 * TH + S / 60)

    fold_positions = np.cumsum(rng.uniform(18, 34, size=15))  
    for fs in fold_positions[fold_positions < s[-1]]:
        depth = rng.uniform(0.15, 0.3)       
        width = rng.uniform(2.0, 3.5)       
        r *= 1 - depth * np.exp(-((S - fs) / width) ** 2)

    polyp_s = [70.0, 150.0, 230.0] 
    polyps = []
    for ps in polyp_s:
        p_theta = rng.uniform(0, 2 * np.pi)
        height, sigma = 6.0, 3.5             # mm
        d_theta = np.angle(np.exp(1j * (TH - p_theta)))   
        dist2 = (S - ps) ** 2 + (RADIUS * d_theta) ** 2   
        r -= height * np.exp(-dist2 / (2 * sigma ** 2))
        polyps.append((np.argmin(np.abs(s - ps)),
                       np.argmin(np.abs(np.angle(np.exp(1j * (theta - p_theta)))))))

    return r, polyps

def fix_normals(mesh, P, C):
    normals = np.asarray(mesh.vertex_normals).reshape(P.shape)
    inward = C[:, None, :] - P                
    score = np.mean(np.sum(normals * inward, axis=-1))
    print("inward score:", score)
    if score < 0:                                  
        tris = np.asarray(mesh.triangles)
        mesh.triangles = o3d.utility.Vector3iVector(tris[:, ::-1])
        mesh.compute_vertex_normals()
    return mesh

if __name__ == "__main__":
    import matplotlib.pyplot as plt
    C = make_centerline()
    T, N1, N2 = make_frames(C)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
    theta = np.linspace(0, 2 * np.pi, NUM_AROUND, endpoint=False)

    r, polyps = make_radius(s, theta)
    plt.imshow(r.T, aspect="auto"); plt.colorbar(label="radius (mm)")
    plt.xlabel("ring"); plt.ylabel("angle index"); plt.show()

    P = make_rings(C, N1, N2, r, theta)
    mesh = fix_normals(make_mesh(P), P, C)
    polyp_xyz = np.array([P[i, j] for i, j in polyps])
    print("polyp positions:\n", polyp_xyz)

    o3d.visualization.draw_geometries([mesh], mesh_show_back_face=True)