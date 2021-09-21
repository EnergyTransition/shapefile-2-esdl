# Heat Network Shapefile to ESDL conversion

This repository contains a script that is able to process a shapefile with lines, discover the topology and generate a connected network description in the ESDL format.

The steps are roughly as follows:

- Read the shapefile contents
- Break up lines in individual line segments
- Collect information about all the end points of the line segments
- Detect overlapping points
- Detect T joints
    - first where the connection ends at the middle of a line segment
    - finally t-joints are added that exist because of 3 line segments beginning (or ending) at the same location
- Generate some shapefiles to be able to visualize the intermediate results
- Discover the topology
- Generate the ESDL containing the connected network

For more details, look into the code itself. The code is well documented.

## Prerequisites

There are two types of requirements
- Standard python packages that are hosted on pypi.org
- Two wheel files (for installing GDAL and Fiona). The current repository contains the wheel files for a 64-bit intel/AMD architecture running Windows. For other architectures the wheel files can be downloaded from https://www.lfd.uci.edu/~gohlke/pythonlibs/. Change the `requirements.txt` file if you want to run this script on another architecture or operating system.

Install the requirements necessary for this script using the following command:

```shell
pip install -r requirements.txt
```

*Note: Refer to this blog post for some excellent instructions on how to manually install GDAL and Fiona on Windows:* https://geoffboeing.com/2014/09/using-geopandas-windows/


## Running the script

At this moment all settings that are required in the script are defined at the top of the source file. Please change these settings to your needs and run the script with the following command:

```shell
python shapefile-processor.py
```

The repository contains an example shapefile from a small part of a Vattenfall district heating network.


## Possible improvements

- Properly detect overlapping lines in a shapefile. The example doesn't contain any overlaps but we've seen other examples
- ...

## Acknowledgements

Thanks to Nico van Ginkel and Rob ten Boden from Vattenfall for the discussions and providing the example shapefile for testing the script.
