/*---------------------------------------------------------------------------*\
  =========                 |
  \\      /  F ield         | OpenFOAM: The Open Source CFD Toolbox
   \\    /   O peration     | Website:  https://openfoam.org
    \\  /    A nd           | Copyright (C) 2011-2022 OpenFOAM Foundation
     \\/     M anipulation  |
-------------------------------------------------------------------------------
License
    This file is part of OpenFOAM.

    OpenFOAM is free software: you can redistribute it and/or modify it
    under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    OpenFOAM is distributed in the hope that it will be useful, but WITHOUT
    ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
    FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License
    for more details.

    You should have received a copy of the GNU General Public License
    along with OpenFOAM.  If not, see <http://www.gnu.org/licenses/>.

Application
    laserbeamFoam_ISW

Description
    Ray-Tracing heat source implementation with two phase incompressible VoF
    description of the metallic substrate and shielding gas phase.

Authors
    Tom Flint, UoM.
    Philip Cardiff, UCD.
    Gowthaman Parivendhan, UCD.
    Joe Robson, UoM.

\*---------------------------------------------------------------------------*/

#include "fvCFD.H"
#include "interfaceCompression.H"
#include "CMULES.H"
#include "EulerDdtScheme.H"
#include "localEulerDdtScheme.H"
#include "CrankNicolsonDdtScheme.H"
#include "subCycle.H"
#include "immiscibleIncompressibleTwoPhaseMixture.H"
#include "noPhaseChange.H"
#include "incompressibleInterPhaseTransportModel.H"
#include "pimpleControl.H"
#include "pressureReference.H"
#include "fvModels.H"
#include "fvConstraints.H"
#include "CorrectPhi.H"
#include "fvcSmooth.H"
#include "Polynomial.H"
#include "laserHeatSource.H"
#include "OFstream.H"

// * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //

int main(int argc, char *argv[])
{
    #include "postProcess.H"

    #include "setRootCaseLists.H"
    #include "createTime.H"
    #include "createMesh.H"
    #include "initContinuityErrs.H"
    #include "createDyMControls.H"
    #include "createFields.H"
    #include "createFieldRefs.H"
    #include "initCorrectPhi.H"
    #include "createUfIfPresent.H"

    if (!LTS)
    {
        #include "CourantNo.H"
        #include "setInitialDeltaT.H"
    }

    // * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * * //
    Info<< "\nStarting time loop\n" << endl;

    while (pimple.run(runTime))
    {
        #include "readControls.H"
        #include "readDyMControls.H"

        // Automated track ID calculation
        label currentTrack = floor(runTime.value() / trackDuration) + 1;

        if (LTS)
        {
            #include "setRDeltaT.H"
        }
        else
        {
            #include "CourantNo.H"
            #include "alphaCourantNo.H"
            #include "setDeltaT.H"
        }

        fvModels.preUpdateMesh();

        // Store divU from the previous mesh so that it can be mapped
        // and used in correctPhi to ensure the corrected phi has the
        // same divergence
        tmp<volScalarField> divU;

        if
        (
            correctPhi
         && !isType<twoPhaseChangeModels::noPhaseChange>(phaseChange)
         && mesh.topoChanged()
        )
        {
            // Construct and register divU for correctPhi
            divU = new volScalarField
            (
                "divU0",
                fvc::div(fvc::absolute(phi, U))
            );
        }

        // Update the mesh for topology change, mesh to mesh mapping
        bool topoChanged = mesh.update();

        // Do not apply previous time-step mesh compression flux
        // if the mesh topology changed
        if (topoChanged)
        {
            talphaPhi1Corr0.clear();
        }

        runTime++;

        Info<< "Time = " << runTime.userTimeName() << nl << endl;

        // --- Pressure-velocity PIMPLE corrector loop
        while (pimple.loop())
        {
            if (pimple.firstPimpleIter() || moveMeshOuterCorrectors)
            {
                if
                (
                    correctPhi
                 && !isType<twoPhaseChangeModels::noPhaseChange>(phaseChange)
                 && !divU.valid()
                )
                {
                    // Construct and register divU for correctPhi
                    divU = new volScalarField
                    (
                        "divU0",
                        fvc::div(fvc::absolute(phi, U))
                    );
                }

                // Move the mesh
                mesh.move();

                if (mesh.changing())
                {
                    gh = (g & mesh.C()) - ghRef;
                    ghf = (g & mesh.Cf()) - ghRef;

                    MRF.update();

                    if (correctPhi)
                    {
                        #include "correctPhi.H"

                        // Update rhoPhi
                        rhoPhi = fvc::interpolate(rho)*phi;
                    }

                    mixture.correct();

                    if (checkMeshCourantNo)
                    {
                        #include "meshCourantNo.H"
                    }
                }

                divU.clear();
            }

            fvModels.correct();

            #include "alphaControls.H"
            #include "alphaEqnSubCycle.H"

            #include "updateProps.H"

            // Update the laser deposition field
            laser.updateDeposition
            (
                alpha_filtered, n_filtered, electrical_resistivity
            );

            turbulence.correctPhasePhi();

            mixture.correct();

            #include "UEqn.H"
            #include "TEqn.H"

            // --- Pressure corrector loop
            while (pimple.correct())
            {
                #include "pEqn.H"
            }

            if (pimple.turbCorr())
            {
                turbulence.correct();
            }
        }

        // Check the cells that have melted
        volScalarField alphaMetal = 
            mesh.lookupObject<volScalarField>("alpha.metal");
        condition = pos(alphaMetal - 0.5) * pos(epsilon1 - 0.5);
        meltHistory += condition;

        forAll(meltTrackID, celli)
        {
            if (condition[celli] > 0.5)
            {
                meltTrackID[celli] = currentTrack;
            }
        }

        scalar moltenMetalVolume = 0.0;

        forAll(meltTrackID, celli)
        {
            if (meltTrackID[celli] > 0.5)
            {
                moltenMetalVolume += mesh.V()[celli];
            }
        }

        reduce(moltenMetalVolume, sumOp<scalar>());

        Info<< "Molten metal volume from meltTrackID = "
            << moltenMetalVolume << " m^3" << nl << endl;

        const scalar inputPower = laser.lastInputPower();
        const scalar depositedPower = laser.lastDepositedPower();
        const scalar absorptivity =
            inputPower > SMALL ? depositedPower/inputPower : 0.0;

        const vector laserPosition = laser.lastLaserPosition();
        const scalar substrateSurfaceY = laserPosition.y();
        const scalar meanCellVolume =
            gSum(mesh.V().field())
           /scalar(returnReduce(mesh.nCells(), sumOp<label>()));
        const scalar cellLength = Foam::pow(meanCellVolume, 1.0/3.0);
        const scalar sectionHalfThickness = 1.5*cellLength;
        const scalar centerHalfWidth = 1.5*cellLength;

        scalar minKeyholeY = GREAT;
        scalar minMeltPoolY = GREAT;
        scalar minMeltPoolX = GREAT;
        scalar maxMeltPoolX = -GREAT;

        forAll(mesh.C(), celli)
        {
            const point& c = mesh.C()[celli];

            if
            (
                mag(c.z() - laserPosition.z()) <= sectionHalfThickness
             && c.y() <= substrateSurfaceY
            )
            {
                if
                (
                    mag(c.x() - laserPosition.x()) <= centerHalfWidth
                 && alphaMetal[celli] <= 0.5
                )
                {
                    minKeyholeY = min(minKeyholeY, c.y());
                }

                if (T[celli] >= TLiquidus[celli])
                {
                    minMeltPoolY = min(minMeltPoolY, c.y());
                    minMeltPoolX = min(minMeltPoolX, c.x());
                    maxMeltPoolX = max(maxMeltPoolX, c.x());
                }
            }
        }

        reduce(minKeyholeY, minOp<scalar>());
        reduce(minMeltPoolY, minOp<scalar>());
        reduce(minMeltPoolX, minOp<scalar>());
        reduce(maxMeltPoolX, maxOp<scalar>());

        const scalar keyholeDepth =
            minKeyholeY < GREAT/2 ? substrateSurfaceY - minKeyholeY : 0.0;
        const scalar meltPoolDepth =
            minMeltPoolY < GREAT/2 ? substrateSurfaceY - minMeltPoolY : 0.0;
        const scalar meltPoolWidth =
            maxMeltPoolX > -GREAT/2 ? maxMeltPoolX - minMeltPoolX : 0.0;

        if (Pstream::master())
        {
            if (moltenPoolVolumeLogPtr.valid())
            {
                moltenPoolVolumeLogPtr()
                    << runTime.value() << ","
                    << moltenMetalVolume
                    << nl;
            }

            if (absorptivityLogPtr.valid())
            {
                absorptivityLogPtr()
                    << runTime.value() << ","
                    << inputPower << ","
                    << depositedPower << ","
                    << absorptivity
                    << nl;
            }

            if (meltPoolGeometryLogPtr.valid())
            {
                meltPoolGeometryLogPtr()
                    << runTime.value() << ","
                    << keyholeDepth*1e6 << ","
                    << meltPoolDepth*1e6 << ","
                    << meltPoolWidth*1e6 << ","
                    << laserPosition.x() << ","
                    << laserPosition.y() << ","
                    << laserPosition.z()
                    << nl;
            }
        }

        runTime.write();

        Info<< "ExecutionTime = " << runTime.elapsedCpuTime() << " s"
            << "  ClockTime = " << runTime.elapsedClockTime() << " s"
            << nl << endl;
    }

    Info<< "End\n" << endl;

    return 0;
}


// ************************************************************************* //
