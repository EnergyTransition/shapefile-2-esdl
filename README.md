# Heat Network Shapefile to ESDL conversion

This repository contains a script that is able to process a shapefile with lines, discover the topology and generate a connected network description in the ESDL format.

The steps are roughly as follows:

- Read the shapefile contents
- Break up lines in individual line segments
- Collect information about all the end points of the line segments
- Detect overlapping points
- Find the closest pipe end for all consumers and producers (Only for 2nd example) 
- Generate some shapefiles to be able to visualize the intermediate results
- Detect T joints
    - first where the connection ends at the middle of a line segment
    - then where producers or consumers must be connected at locations where 2 line segments 'touch' (Only for 2nd example)
    - finally t-joints are added that exist because of 3 line segments beginning (or ending) at the same location
- Generate some more shapefiles to be able to visualize the intermediate results
- Discover the topology
- Mark the direction of pipes based on location of producers and/or consumers (Only for 2nd example)
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


## Two examples

# Example 1: Part of a district heating network in Ede (Vattenfall)

The script was originally developed using the data from the first example as an input. It contains part of a
district heating network in Ede. It's one shapefile with lines representing both the supply network as the return
network.

![The input shapefile](./docs/Double%20pipe%20network%20shapefile.png)

![The details of the input shapefile](./docs/Double%20pipe%20network%20shapefile%20details.png)

The resulting ESDL that is generated after running the script, looks like this:

![The resulting ESDL](./docs/ESDL%20double%20pipe%20network%20output%20.png)

# Example 2: Part of a disctrict heating network in the Westland (Capturam)

The script was extended using the second example as an input. The second input allows you to specify three different
shapefiles (one for the pipes, one for the producers and one for the consumers.

Note: At the moment, it's only possible to convert shapefiles that represent a single pipe network (so only the supply
network and no return network)!

![The input shapefile](./docs/WNW%20shapefiles.png)

The resulting ESDL that is generated after running the script, looks like this:

![The resulting ESDL](./docs/ESDL%20WNW%20output.png)


## Possible improvements

- Properly detect overlapping lines in a shapefile. The example doesn't contain any overlaps but we've seen other examples
- Improve support for 2D/3D shapefiles (with and without Z coordinates)
- Handle consumer and producer connecting at same point
- Handle simple network without T-joints
- ...

## Acknowledgements

- Thanks to Nico van Ginkel and Rob ten Boden from Vattenfall for the discussions and providing the first example shapefile for testing the script.
- Thanks to Thijmen Vosmer (Capturam) and Mark Supper (Rotterdam Engineering) for the discussions and providing the second example.
