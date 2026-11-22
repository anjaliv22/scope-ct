import numpy as np
import matplotlib.pyplot as plt

stats = np.load("stats.npy")              # (250, 6)
true_poses = np.load("true_poses.npy")    # (250, 4, 4)
est_poses = np.load("est_poses.npy")      # (250, 4, 4)

t_err, r_err, ms = stats[:, 0], stats[:, 1], stats[:, 2]
frames = np.arange(len(stats))

true_xyz = true_poses[:, :3, 3]           # camera positions over time (250, 3)
est_xyz = est_poses[:, :3, 3]

fig, ax = plt.subplots(2, 2, figsize=(11, 7))

# 1. Position error
ax[0, 0].plot(frames, t_err)
ax[0, 0].axhline(1.0, color="red", linestyle="--", label="1 mm")
ax[0, 0].set(title="Position error", xlabel="frame", ylabel="mm")
ax[0, 0].legend()

# 2. Rotation error
ax[0, 1].plot(frames, r_err, color="tab:orange")
ax[0, 1].set(title="Rotation error", xlabel="frame", ylabel="degrees")

# 3. Time per frame
ax[1, 0].plot(frames, ms, color="tab:green")
ax[1, 0].axhline(33, color="red", linestyle="--", label="33 ms (30 fps)")
ax[1, 0].set(title="ICP time per frame", xlabel="frame", ylabel="ms")
ax[1, 0].legend()

# 4. Path seen from above (x vs y)
ax[1, 1].plot(true_xyz[:, 0], true_xyz[:, 1], label="true", linewidth=3, alpha=0.5)
ax[1, 1].plot(est_xyz[:, 0], est_xyz[:, 1], "--", label="ICP estimate")
ax[1, 1].set(title="Scope path (top view)", xlabel="x (mm)", ylabel="y (mm)")
ax[1, 1].axis("equal")
ax[1, 1].legend()

fig.suptitle(f"Scope tracking: mean {t_err.mean():.2f} mm / {r_err.mean():.2f}°, "
             f"{ms.mean():.0f} ms per frame, {int(stats[:, 5].sum())} lost frames")
fig.tight_layout()
fig.savefig("results.png", dpi=150)       # for your README
plt.show()