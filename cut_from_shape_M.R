##################################################################################
## Filename : cut_from_shape_M.R                                                 #
## This R script was designed to extract the specific shape from the larger area # 
## based on the georeferenced shape file                                         #
## Created by: Biagio Sileo & Htay Htay Aung                                     #
## The code is created for Open Research                                         #
##################################################################################

library(terra)  # Load the 'terra' package for raster and vector data manipulation

##=========================== Folder paths ======================================
input_root <- "D:/inputfolder"  # Folder containing .asc raster files
shape_dir   <- "D:/shapfile_folder"   # Folder containing shapefiles for clipping
output_root <- "D:/outputfolder"  # Output folder for clipped rasters
dir.create(output_root, showWarnings = FALSE, recursive = TRUE)  # Create output folder if it doesn’t exist

##========================== List .asc raster files and shapefiles ==============
files <- list.files(input_root, pattern = "\\.asc$", full.names = TRUE, recursive = TRUE)  # Get all .asc raster files
shp <- list.files(shape_dir, pattern = "shapefile.shp", full.names = TRUE)  # Get all shapefiles in the directory

shape_name <- tools::file_path_sans_ext(basename(shp))  # Extract shapefile name without extension
message("Processing shape: ", shape_name)  # displaying the files to be cut
    
shape <- vect(shp)  # Load the shapefile as a SpatVector
crs(shape) <- "EPSG:3035"  # Ensure it has the correct CRS 
    
#========================== Create output subdirectory for the current shape======
shape_output_dir <- file.path(output_root, shape_name)
dir.create(shape_output_dir, showWarnings = FALSE, recursive = TRUE)

#========================== Loop through each raster file ========================
for (f in files) {
    raster_name <- tools::file_path_sans_ext(basename(f))  # Get raster name without extension
    message("Processing raster: ", raster_name)  # Informative message
    
    r <- rast(f)  # Load the raster
    crs(r) <- "EPSG:3035"  # Set CRS if missing (should match the shape CRS)
    
    # Crop the raster to the extent of the shape (cuts outside bounding box)
    r_crop <- crop(r, shape)
    # Mask the raster using the shape (sets outside shape area to NA); touches=TRUE includes cells partially intersected
    r_mask <- mask(r_crop, shape, touches = FALSE)
    
    parameter_name <- "Runoff"
    short_name <- sub("^[^_]*_", "", raster_name)
    #short_name <- sub(".*(A\\d{7}).*_SUD", "\\1", raster_name)
    shape_label <- "Turbolo"  # Dynamically name output
    
    out_file <- file.path(shape_output_dir, paste0(parameter_name, "_", shape_label, "_", short_name, ".asc"))
    writeRaster(r_mask, out_file, overwrite = TRUE)
}

message("\n All files have been successfully clipped!")