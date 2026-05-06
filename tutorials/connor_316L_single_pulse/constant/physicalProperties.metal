/*--------------------------------*- C++ -*----------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Version:  10
     \\/     M anipulation  |
\*---------------------------------------------------------------------------*/
FoamFile
{
    format      ascii;
    class       dictionary;
    location    "constant";
    object      physicalProperties.water;
}
// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

viscosityModel  constant;

nu               7e-7;

rho              7904;

elec_resistivity	9e-7;

table_kappa
(
    (300    14.68)
    (500    17.60)
    (800    21.98)
    (1200   27.82)
    (1658   34.51)
    (1723   26.90)
    (2500   26.90)
    (5000   26.90)
);

table_cp
(
    (300    492.8)
    (500    540.8)
    (800    612.8)
    (1200   708.8)
    (1658   818.7)
    (1723   790.0)
    (2500   790.0)
    (5000   790.0)
);




   
Tsolidus 1658;
Tliquidus 1723;
LatentHeat 260e3;
beta    1.8e-5;

// Heat Transfer Properties for Space Welding
emissivity      0.26;
T_ambient       300.0;
h_convection    0.0;


// ************************************************************************* //
