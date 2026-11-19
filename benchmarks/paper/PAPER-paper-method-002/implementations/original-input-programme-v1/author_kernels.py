"""Literal author helper extraction; source only at preparation time.

Bodies from bc_output notebook cells7/8/9/11/13 and stimuli_meta cell7.
Only four-space nesting is added. NumPy, author JAX convolve2d, cell geometry,
and pixel_size are supplied by the separately admitted caller. No import,
file access, numerical execution or authority selection occurs at module load.

Source notebooks:
  bc_output.body: 51539f56a68285e6a8e60d29a744ddaafb3032aa6f8492f144ee015a6dfe74b4
  stimuli_meta.body: d43f1e66b6f8ab36d1747c920a5b620f2b64ef773d682af3bcc2aef80fe9fa34
"""


def make_author_kernels(np, convolve2d, cell, pixel_size=30):
    """Return unchanged author callables with explicit source-global bindings."""
    # BEGIN LITERAL BC CELLS 7, 8, 9, 11, 13
    def center_surround_filter(spatial_axis, std1=50, std2=200):
        amp1 = 1 / std1
        gaussian1 = amp1 * np.exp(-spatial_axis**2 / std1**2)
        
        amp2 = 1 / std2
        gaussian2 = amp2 * np.exp(-spatial_axis**2 / std2**2)
        
        spatial_kernel = gaussian1 - gaussian2
        return spatial_kernel
    
    
    def gaussian_filter(spatial_axis, std=50):
        amp1 = 1 / std
        gaussian1 = amp1 * np.exp(-spatial_axis**2 / std**2)
        return gaussian1
    
    
    # spatial_axis = np.linspace(-600, 600, 1000)
    # center_surround_kernel = center_surround_filter(spatial_axis)
    # gaussian_kernel = gaussian_filter(spatial_axis)
    
    # fig, ax = plt.subplots(1, 2, figsize=(6, 2))
    # _ = ax[0].plot(spatial_axis, center_surround_kernel)
    # _ = ax[1].plot(spatial_axis, gaussian_kernel)
    def upsample_image(image, pixel_size, kernel_size):
        """Returns a new image where every value is one micro meter in size."""
        image = np.repeat(image, (pixel_size,), axis=0)
        image = np.repeat(image, (pixel_size,), axis=1)
        image_full = np.zeros((image.shape[0] + 2*kernel_size - 1, image.shape[1] + 2*kernel_size - 1))
        image_full[kernel_size:-kernel_size+1,kernel_size:-kernel_size+1] = image 
        return image_full
    def build_opl_kernel(filter: str, std, filter_size):
        res_filter = 100
        center = [0., 0.]
        
        pos_x = np.linspace(-filter_size, filter_size, res_filter)
        pos_y = np.linspace(-filter_size, filter_size, res_filter)
        X, Y = np.meshgrid(pos_x, pos_y)
        
        dist_x = center[0] - X
        dist_y = center[1] - Y
        
        dists = np.sqrt(dist_x**2 + dist_y**2)
    
        if filter == "Gaussian":
            kernel = gaussian_filter(dists, std) / 100.0
        elif filter == "center_surround":
            raise NotImplementedError
            kernel = center_surround_filter(dists) / 100.0
        else:
            raise ValueError
    
        return kernel
    
    def opl(image, kernel):
        """Performs linear spatial filtering with a provided kernel."""
        bc_input = convolve2d(image, kernel, mode="valid")
        return bc_input
    class BipolarCell:
        """Given input current, return output of bipolar cells."""
    
        def __init__(self, max_input):
            self.x_vals = [-100, -50, -25, -12.5, -6.75, -3, 3, 6.75, 12.5, 25.0, 50.0, 100.0]
            self.response = [-0.05, -0.12, -0.15, -0.1, -0.08, -0.03, 0.1, 0.18, 0.37, 0.64, 0.85, 1.0]
            self.intensity = (1.0 + 1.0 / 100 * np.asarray(self.x_vals)) / 2.0
    
            # To scale the input-output curve, we have to know the maximal input current.
            self.max_input = max_input
    
        def __call__(self, input):
            standardized_bc_input = input / self.max_input
            bc_output = np.interp(standardized_bc_input, self.intensity, self.response)
            return bc_output
    def get_bc_cell_locations(spacing, bc_grid_size_x, bc_grid_size_y):
        """Return x- and y-location of BCs at origin zero.
        
        Args:
            spacing: Distance between BCs (in um).
        """
        gap_x = spacing
        gap_y = np.sqrt(gap_x ** 2 - (gap_x/2) **2)
        x_locs = np.arange(0, bc_grid_size_x, gap_x)
        y_locs = np.arange(0, bc_grid_size_y, gap_y)
        
        all_x_locs, all_y_locs = np.meshgrid(x_locs, y_locs)
        all_x_locs[::2] += gap_x / 2
        
        all_x_locs = all_x_locs.flatten()
        all_y_locs = all_y_locs.flatten()
    
        return all_x_locs, all_y_locs
    
    
    def move_bc_locations(x_loc_bipolar, y_loc_bipolar, x_move, y_move):
        """Move the locations of the bipolar cells to the image center."""
        # TODO: need to move it to the center of the cell, and the grid of BCs has to cover the whole space.
        bc_loc_x = x_loc_bipolar + x_move
        bc_loc_y = y_loc_bipolar + y_move
        return bc_loc_x, bc_loc_y
    
    
    def get_image_locs(df):
        im_pos_x = np.linspace(-7.5*pixel_size + 0.5, 7.5*pixel_size - 0.5, 15*pixel_size) + df["image_center_x"].item()
        im_pos_y = -np.linspace(-10.0*pixel_size + 0.5, 10.0*pixel_size - 0.5, 20*pixel_size) + df["image_center_y"].item()
        return im_pos_x, im_pos_y
    
    
    def discretize_bc_output(bc_output, bc_loc_x, bc_loc_y, im_pos_x, im_pos_y):
        """Given the (almost continuous) BC output grid, compute the position of BC cells."""
        pixel_size = 30  # um
        
        grid_x, grid_y = np.meshgrid(im_pos_x, im_pos_y)
        
        dists = []
        output_vals_at_bc_loc = []
        
        for x, y in zip(bc_loc_x, bc_loc_y):
            dist_x = (grid_x - x)**2
            dist_y = (grid_y - y)**2
            dist = np.sqrt(dist_x + dist_y)
            min_ind = np.unravel_index(np.argmin(dist), dist.shape)
            dists.append(min_ind)
            output_vals_at_bc_loc.append(bc_output[min_ind])
        
        dists = np.asarray(dists)
        
        # Standardize to [0, 1] range.
        output_vals_at_bc_loc = output_vals_at_bc_loc - np.min(output_vals_at_bc_loc)
        output_vals_at_bc_loc = output_vals_at_bc_loc / np.max(output_vals_at_bc_loc)
    
        return output_vals_at_bc_loc
    # END LITERAL BC CELLS 7, 8, 9, 11, 13
    # BEGIN LITERAL STIMULI CELL 7
    def compute_jaxley_stim_locations(x, y):
        """For a given (x,y) location, return all branch and compartment inds within a specified distance."""
        min_dists = []
        min_comps = []
        branch_inds_in_pixel = []
        comps_in_pixel = []
        min_dist_of_branch_in_pixel = []
    
        for i, xyzr in enumerate(cell.xyzr):
            dists = np.sqrt((x - xyzr[:, 0])**2 + (y - xyzr[:, 1])**2)
            is_in_reach = np.min(dists) < 20  # 20 um
    
            if is_in_reach:
                branch_inds_in_pixel.append(i)
                min_dist_of_branch_in_pixel.append(np.min(dists))
                
                argmin_dist = np.argmin(dists)
                if len(dists) > 1:
                    comp = argmin_dist / (len(dists) - 1)
                else:
                    comp = 0.5
                comps_in_pixel.append(comp)
                
        return branch_inds_in_pixel, comps_in_pixel, min_dist_of_branch_in_pixel
    # END LITERAL STIMULI CELL 7
    return {
        "center_surround_filter": center_surround_filter,
        "gaussian_filter": gaussian_filter,
        "upsample_image": upsample_image,
        "build_opl_kernel": build_opl_kernel,
        "opl": opl,
        "BipolarCell": BipolarCell,
        "get_bc_cell_locations": get_bc_cell_locations,
        "move_bc_locations": move_bc_locations,
        "get_image_locs": get_image_locs,
        "discretize_bc_output": discretize_bc_output,
        "compute_jaxley_stim_locations": compute_jaxley_stim_locations,
    }
