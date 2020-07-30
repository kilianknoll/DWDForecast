dwdforecast
==========



Introduction
------------

This library provides a  Python interface to access DWD weatherforecast data to project solar power generation:
It will extract the following data from a MOSMIX file -see further down below for specifications
* Rad1h
* TTT
* PPPP
* FF

It has been tested with Python version 3.5, 3.6, 3.7 and 3.8.

Tested with 
~~~~~~~~~~~~~~~~

* Raspberry & Windows



Installation
------------
Clone / Download repo and use dwdforecast.py 


Configuration
------------

To adapt to your needs - familiarize yourself with the content of data we are about to parse  (Keyword : Mosmix):
https://www.dwd.de/DE/leistung…_blob=publicationFile&v=3

List of available (virtual) weatherstations:
https://www.dwd.de/DE/leistung…=nasPublication&nn=495490

Please check the closest weatherstation to your location:
https://wettwarn.de/mosmix/mosmix.html

Once you found the closest station, note the number and change the python script in the inline comments to your needs


python dwdforecast.py

Features
~~~~~~~~

* Provide Class that reads the weatherstation via a seperate thread and create a list of forementioned data 
* Supports two modes of operation
*   Simple : will query the DWD internet site once and pull the data
*   Complex: will run in a continuous loop to gather data and download when updates are available 




Disclaimer
---------------


.. Warning::

Please note that you are responsible to operate this program and comply with regulations imposed on you by other Website providers (such as the DWD website being polled)

Therefore, the author does not provide any guarantee or warranty concerning to correctness, functionality or performance and does not accept any liability for damage caused by this module, examples or mentioned information.

   **Thus, use it on your own risk!**

License
-------

Distributed under the terms of the GNU General Public License v3.