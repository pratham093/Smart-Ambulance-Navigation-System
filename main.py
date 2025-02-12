from fastapi import FastAPI, Depends, HTTPException, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import models, schemas
from database import engine, get_db, SessionLocal
import logging
from typing import List
import traci  
from fastapi.staticfiles import StaticFiles
import os

#logger = logging.getLogger(__name__)

app = FastAPI()

# Set up Jinja2 templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

#SUMO GUI
SUMO_BINARY = "sumo-gui" 
SUMO_CONFIG_FILE = "E:/fyp/code/SUMO_V4/osm.sumocfg"

def start_sumo():
    """Start SUMO if it's not already running."""
    if not traci.isRunning():
        traci.start([SUMO_BINARY, "-c", SUMO_CONFIG_FILE])
        print("✅ SUMO started.")

def add_poi_to_sumo(id: str, x: float, y: float, color=(0, 0, 255)):
    """Add a POI (Point of Interest) to SUMO."""
    start_sumo()
    traci.poi.add(id, x, y, color, layer=1)
    print(f"📍 POI {id} added at ({x}, {y})")

def mark_patient_location(latitude, longitude):
    """Mark a patient's location using a red POI in SUMO."""
    start_sumo()

    patient_id = "patient_marker"
    patient_color = (255, 0, 0)  # Red color

    # Remove existing patient marker if it exists
    if patient_id in traci.poi.getIDList():
        traci.poi.remove(patient_id)

    # Add new patient marker
    traci.poi.add(patient_id, longitude, latitude, patient_color, layer=2)
    print(f"🚑 Patient location marked at ({latitude}, {longitude}) in SUMO.")
# Create tables in the database
models.Base.metadata.create_all(bind=engine)

# HTML Route to display hospitals and ambulances
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request, db: Session = Depends(get_db)):
    hospitals = db.query(models.Hospital).all()
    ambulances = db.query(models.Ambulance).all()
    return templates.TemplateResponse("index.html", {"request": request, "hospitals": hospitals, "ambulances": ambulances})

#client side
@app.post("/request_ambulance/")
async def request_ambulance(request: schemas.AmbulanceRequest, db: Session = Depends(get_db)):
    # Find patient by hospital_id (assuming it's unique)
    hospital = db.query(models.Hospital).filter(models.Hospital.id == request.hospital_id).first()

    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    # Parse the client location (latitude, longitude)
    latitude, longitude = map(float, request.client_location.split(","))
    
    # Optionally, update hospital location if needed
    hospital.latitude = latitude
    hospital.longitude = longitude
    db.commit()
    db.refresh(hospital)

    return {"message": "Request submitted and location updated", "hospital_id": hospital.id, "latitude": latitude, "longitude": longitude}

# Create a hospital and return updated list of hospitals
@app.post("/hospitals/", response_model=list[schemas.HospitalResponse])
async def create_hospital(hospital: schemas.HospitalCreate, db: Session = Depends(get_db)):
    new_hospital = models.Hospital(**hospital.dict())
    db.add(new_hospital)
    db.commit()
    db.refresh(new_hospital)
    return db.query(models.Hospital).all()

# Get all hospitals
@app.get("/hospitals/", response_model=list[schemas.HospitalResponse])
async def get_hospitals(db: Session = Depends(get_db)):
    return db.query(models.Hospital).all()

# Create an ambulance and return updated list of ambulances
@app.post("/ambulances/", response_model=List[schemas.AmbulanceResponse])
def create_ambulance(ambulance: schemas.AmbulanceCreate, db: Session = Depends(get_db)):
    db_ambulance = models.Ambulance(**ambulance.model_dump())  # Use .model_dump() in Pydantic v2
    db.add(db_ambulance)
    db.commit()
    db.refresh(db_ambulance)
    return db_ambulance 

# # Define FastAPI route
# @app.post("/submit_ambulance")
# async def submit_ambulance(ambulance: schemas.AmbulanceCreate, db: SessionLocal = Depends()):
#     new_ambulance = models.Ambulance(**ambulance.model_dump())  
#     db.add(new_ambulance)
#     db.commit()
#     db.refresh(new_ambulance)
#     return {"message": "Ambulance added successfully", "ambulance": new_ambulance}

# Handle ambulance post request from the HTML form@app.post("/submit_ambulance")

@app.post("/submit_ambulance", response_class=HTMLResponse)
async def submit_ambulance(
    name: str = Form(...),
    hospital_id: int = Form(...),
    vehicle_number: str = Form(...),
    current_location: str = Form(...),
    db: Session = Depends(get_db)
):
    # Log the incoming form data
    logging.info(f"Received Form Data - name: {name}, hospital_id: {hospital_id}, vehicle_number: {vehicle_number}, current_location: {current_location}")

    try:
        # Create the AmbulanceCreate schema from form data
        ambulance_data = schemas.AmbulanceCreate(
        ambulance_name=name,
        hospital_id=hospital_id,
        vehicle_number=vehicle_number,
        current_location=current_location
    )
        # Create the ambulance entry in the database (awaiting the async function)
        created_ambulance = create_ambulance(db=db, ambulance=ambulance_data)

        # Log the created ambulance
        logging.info(f"Ambulance created successfully: {created_ambulance}")

        # Return a success message with a link to go back to the homepage
        return HTMLResponse(content="<h2>Ambulance Added Successfully</h2><a href='/'>Go back</a>", status_code=200)
    
    except Exception as e:
        # Log any errors
        logging.error(f"Error occurred while creating ambulance: {e}")
        # Return an error message
        return HTMLResponse(content="<h2>Error occurred while adding the ambulance.</h2><a href='/'>Go back</a>", status_code=500)
    
# Get all ambulances
@app.get("/ambulances/", response_model=list[schemas.AmbulanceResponse])
async def get_ambulances(db: Session = Depends(get_db)):
    return db.query(models.Ambulance).all()

# HTML Form for adding new hospital
@app.get("/add_hospital", response_class=HTMLResponse)
async def add_hospital_form(request: Request):
    return templates.TemplateResponse("add_hospital.html", {"request": request})

# HTML Form for adding new ambulance
@app.get("/add_ambulance", response_class=HTMLResponse)
async def add_ambulance_form(request: Request):
    return templates.TemplateResponse("add_ambulance.html", {"request": request})

# Handle hospital post request from the HTML form
@app.post("/submit_hospital", response_class=HTMLResponse)
async def submit_hospital(name: str = Form(...), location: str = Form(...), db: Session = Depends(get_db)):
    hospital = schemas.HospitalCreate(name=name, location=location)
    await create_hospital(hospital, db)
    return HTMLResponse(content="<h2>Hospital Added Successfully</h2><a href='/'>Go back</a>", status_code=200)

@app.post("/submit_request/")
async def submit_request(request: schemas.AmbulanceRequest, db: Session = Depends(get_db)):
    # Find the hospital by hospital_id
    hospital = db.query(models.Hospital).filter(models.Hospital.id == request.hospital_id).first()

    if not hospital:
        raise HTTPException(status_code=404, detail="Hospital not found")

    return {"message": "Ambulance request successfully submitted", "hospital_id": hospital.id}

@app.post("/update_patient_location/")
def update_patient_location(
    patient_name: str = Form(...), 
    phone_number: str = Form(...), 
    latitude: float = Form(...), 
    longitude: float = Form(...), 
    db: Session = Depends(get_db)
):
    # Check if patient exists by phone number
    existing_patient = db.query(models.Patient).filter(models.Patient.phone_number == phone_number).first()

    if existing_patient:
        # Update existing patient location
        existing_patient.latitude = latitude
        existing_patient.longitude = longitude
        db.commit()
        message = "Patient location updated successfully"
    else:
        # Create new patient
        new_patient = models.Patient(name=patient_name, phone_number=phone_number, latitude=latitude, longitude=longitude)
        try:
            db.add(new_patient)
            db.commit()
            db.refresh(new_patient)
            message = "New patient added successfully"
        except IntegrityError:
            db.rollback()
            raise HTTPException(status_code=400, detail="Patient with this phone number already exists")

    # **Start SUMO with the patient's location marked**
    mark_patient_location(latitude, longitude)

    return {"message": message}

@app.post("/add_poi")
async def add_poi(id: str, x: float, y: float):
    try:
        add_poi_to_sumo(id, x, y, (0, 0, 255))  # Default: Blue
        return {"message": f"POI {id} added at ({x}, {y})"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/update_sumo")
async def update_sumo(location: schemas.LocationUpdate):
    # Command to update SUMO (Modify based on your setup)
    sumo_command = f"sumo-gui --net-file=my_network.net.xml --trip-file=trips.trips.xml --start --lat={location.lat} --lon={location.lon}"
    
    # Run SUMO command (modify as needed)
    os.system(sumo_command)

    return {"message": f"SUMO updated with location ({location.lat}, {location.lon})"}

# @app.post("/add_poi")
# async def add_poi(poi: POI):
#     try:
#         add_poi_to_sumo(poi.id, poi.x, poi.y, (0, 0, 255))  # Default: Blue
#         return {"message": f"POI {poi.id} added at ({poi.x}, {poi.y})"}
#     except Exception as e:
#         return {"error": str(e)}