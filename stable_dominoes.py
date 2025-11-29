# ===========================================================================
# Project 5: Domino Reveal (Final Tweaked Version)
# Author: Isaac Harfst
# Class: CS 417
# ===========================================================================

import maya.cmds as cmds
import maya.api.OpenMaya as om

def get_name(node):
    if isinstance(node, list) or isinstance(node, tuple):
        return node[0]
    return node

def run_stable_dominoes():
    # 1. NUCLEAR CLEANUP
    # ---------------------------------------------------------
    print("Cleaning scene...")
    # Delete physics nodes first
    if cmds.objExists('rigidSolver'):
        cmds.delete('rigidSolver')
    
    cleanup_list = [
        'Domino_Group',
        'Ground_Plane',
        'Physics_Helpers',
        'Domino_Cam',
        'domino_gravityField',
        'temp_image_node',
        'temp_place_node',
        'Light_Group',
        'Side_Pusher'
    ]
    for obj in cleanup_list:
        if cmds.objExists(obj):
            cmds.delete(obj)
            
    # Delete rigid bodies safely
    rbs = cmds.ls(type='rigidBody')
    if rbs:
        cmds.delete(rbs)

    # Delete cameras
    cams = cmds.ls("Domino_Cam*")
    if cams:
        cmds.delete(cams)
    
    # Delete materials
    old_mats = cmds.ls("pixelMat_*") + cmds.ls("dominoMat_Base*") + cmds.ls("Ground_Black_Mat")
    if old_mats:
        cmds.delete(old_mats)

    # 2. GET IMAGE
    # ---------------------------------------------------------
    file_path = cmds.fileDialog2(fileMode=1, caption="Select Image (20x20)")
    if not file_path:
        cmds.warning("Cancelled.")
        return
    image_file = file_path[0]

    file_node = cmds.shadingNode('file', asTexture=True, name='temp_image_node')
    place_node = cmds.shadingNode('place2dTexture', asUtility=True, name='temp_place_node')
    cmds.connectAttr(place_node + '.outUV', file_node + '.uvCoord')
    cmds.setAttr(file_node + '.fileTextureName', image_file, type='string')

    # 3. TIMELINE
    # ---------------------------------------------------------
    cmds.playbackOptions(min=1, max=400, ast=1, aet=400)
    cmds.currentTime(1)

    # 4. PHYSICS GLOBAL
    # ---------------------------------------------------------
    # Force new solver creation by making a temp active rigid body
    temp = cmds.polyCube()[0]
    cmds.rigidBody(temp, active=True)
    cmds.delete(temp)
    
    # Set solver precision
    if cmds.objExists('rigidSolver'):
        cmds.setAttr("rigidSolver.stepSize", 0.01)
        cmds.setAttr("rigidSolver.collisionTolerance", 0.01)

    # 5. BUILD FLOOR (PASSIVE RIGID BODY THAT DOESN'T FALL)
    # ---------------------------------------------------------
    ground = get_name(cmds.polyPlane(w=150, h=150, n="Ground_Plane"))
    cmds.move(0, -0.2, 0, ground)
    
    # Black Material
    blk_shd = cmds.shadingNode('lambert', asShader=True, n="Ground_Black_Mat")
    cmds.setAttr(blk_shd + ".color", 0.05, 0.05, 0.05, type="double3")
    blk_sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, n="Ground_Black_SG")
    cmds.connectAttr(blk_shd + ".outColor", blk_sg + ".surfaceShader")
    cmds.sets(ground, forceElement=blk_sg)

    # PASSIVE Rigid Body – explicitly frozen
    ground_rb = get_name(cmds.rigidBody(
        ground,
        active=False,
        name="RB_Ground",
        bounciness=0.0
    ))

    # Make sure the solver treats it as an immovable object
    if cmds.attributeQuery("active", node=ground_rb, exists=True):
        cmds.setAttr(ground_rb + ".active", 0)
    if cmds.attributeQuery("mass", node=ground_rb, exists=True):
        cmds.setAttr(ground_rb + ".mass", 0.0)
    if cmds.attributeQuery("useGravity", node=ground_rb, exists=True):
        cmds.setAttr(ground_rb + ".useGravity", 0)

    cmds.setAttr(ground_rb + ".staticFriction", 0.9)
    cmds.setAttr(ground_rb + ".dynamicFriction", 0.9)

    # Lock transforms on the transform node (extra safety)
    for attr in ['.tx', '.ty', '.tz', '.rx', '.ry', '.rz']:
        cmds.setAttr(ground + attr, lock=True)

    # 6. GRAVITY (ISOLATED)
    # ---------------------------------------------------------
    # Clear selection to ensure gravity doesn't connect to floor
    cmds.select(clear=True)
    gravity_field = get_name(cmds.gravity(n='domino_gravityField', pos=(0, 0, 0), magnitude=25.0))

    # 7. BUILD DOMINOES (EVERY CELL HAS A DOMINO, COLOR FROM IMAGE)
    # ---------------------------------------------------------
    main_grp = cmds.group(em=True, n="Domino_Group")
    domino_list = []
    
    width = 20
    height = 20
    spacing = 0.8 
    
    offset_x = (width * spacing) / 2.0
    offset_z = (height * spacing) / 2.0

    print("Generating Dominoes...")
    
    for y in range(height):
        for x in range(width):
            u_val = (x + 0.5) / width
            v_val = (y + 0.5) / height
            color = cmds.colorAtPoint(file_node, u=u_val, v=v_val, output='RGB')
            r, g, b = color[0], color[1], color[2]
            
            name = f"domino_{x}_{y}"
            dom = get_name(cmds.polyCube(w=0.2, h=1.0, d=0.5, n=name))
            
            pos_x = (x * spacing) - offset_x
            pos_z = (y * spacing) - offset_z 
            cmds.move(pos_x, 0.5, pos_z, dom)
            
            # One material per domino, using the pixel color
            shd_name = f"pixelMat_{x}_{y}"
            if not cmds.objExists(shd_name):
                shd = cmds.shadingNode('lambert', asShader=True, n=shd_name)
                cmds.setAttr(f"{shd}.color", r, g, b, type='double3')
                sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, n=f"{shd_name}SG")
                cmds.connectAttr(f"{shd}.outColor", f"{sg}.surfaceShader")
                cmds.sets(dom, forceElement=sg)

            try:
                # Active Rigid Body
                dom_rb = get_name(cmds.rigidBody(
                    dom,
                    active=True,
                    mass=0.5,
                    bounciness=0.0,
                    damping=0.05
                ))
                
                cmds.setAttr(dom_rb + ".staticFriction", 0.5)
                cmds.setAttr(dom_rb + ".dynamicFriction", 0.5)
                
                # CONNECT GRAVITY (Only to dominoes)
                cmds.connectDynamic(dom, f=gravity_field)
                
                domino_list.append(dom)
                cmds.parent(dom, main_grp)
            except:
                # Legacy rigid body can be touchy; skip if it throws.
                pass

    # Clean up temp image nodes
    if cmds.objExists(file_node):
        cmds.delete(file_node)
    if cmds.objExists(place_node):
        cmds.delete(place_node)

    # 8. SIDE PUSHER (ACTIVE BODY WITH MORE FORCE, INVISIBLE)
    # ---------------------------------------------------------
    if not cmds.objExists('Physics_Helpers'):
        cmds.group(em=True, n='Physics_Helpers')

    # Create Pusher (Thick Block)
    pusher = get_name(cmds.polyCube(
        w=3.0,                             # front thickness
        h=1.5,
        d=height * spacing + 4,            # covers whole row
        n="Side_Pusher"
    ))
    
    # Start left of the leftmost domino
    start_x = -offset_x - 3.0   # e.g., ~ -11.0
    cmds.move(start_x, 0.75, 0, pusher, absolute=True)
    
    # ACTIVE rigid body with stronger hit
    pusher_rb = get_name(cmds.rigidBody(
        pusher,
        active=True,
        name="Pusher_RB",
        bounciness=0.0,
        damping=0.05      # lower damping -> more sustained motion
    ))
    if cmds.attributeQuery("mass", node=pusher_rb, exists=True):
        cmds.setAttr(pusher_rb + ".mass", 4.0)      # heavier -> stronger collision
    if cmds.attributeQuery("useGravity", node=pusher_rb, exists=True):
        cmds.setAttr(pusher_rb + ".useGravity", 0)

    # Stronger shove along +X so it pushes the first column cleanly
    if cmds.attributeQuery("initialVelocityX", node=pusher_rb, exists=True):
        cmds.setAttr(pusher_rb + ".initialVelocityX", 5.0)

    # Invisible in renders: set primaryVisibility on shape
    pusher_shapes = cmds.listRelatives(pusher, shapes=True) or []
    for shape in pusher_shapes:
        if cmds.attributeQuery("primaryVisibility", node=shape, exists=True):
            cmds.setAttr(shape + ".primaryVisibility", 0)

    cmds.parent(pusher, 'Physics_Helpers')

    # 9. CAMERA (TOP DOWN)
    # ---------------------------------------------------------
    cam_name = "Domino_Cam"
    if not cmds.objExists(cam_name):
        cam = get_name(cmds.camera(n=cam_name)[0])
        cam_shape = cmds.listRelatives(cam, shapes=True)[0]
        cmds.setAttr(f"{cam_shape}.renderable", 1)
        
        # Position high up
        cmds.move(0, 60, 0, cam, absolute=True)
        # Rotate to look straight down
        cmds.rotate(-90, 0, 0, cam, absolute=True)
        
        try:
            cmds.lookThru(cam)
        except:
            pass

    # 10. LIGHTING
    # ---------------------------------------------------------
    light_grp = cmds.group(em=True, n="Light_Group")
    
    key_l = get_name(cmds.directionalLight(intensity=1.5))
    key_t = cmds.listRelatives(key_l, p=True)[0]
    cmds.setAttr(f"{key_t}.rotate", -60, -30, 0, type="double3")
    cmds.setAttr(f"{key_t}.useDepthMapShadows", 1)
    cmds.parent(key_t, light_grp)
    
    fill_l = get_name(cmds.directionalLight(intensity=0.8))
    fill_t = cmds.listRelatives(fill_l, p=True)[0]
    cmds.setAttr(f"{fill_t}.rotate", -45, 120, 0, type="double3")
    cmds.parent(fill_t, light_grp)

    # 11. BAKE
    # ---------------------------------------------------------
    print("Baking physics... (Wait for it)")
    if domino_list:
        cmds.bakeResults(
            domino_list,
            simulation=True,
            t=(1, 360),
            sampleBy=1,
            disableImplicitControl=True,
            preserveOutsideKeys=True
        )
    print("Baking Complete.")

    # 12. RENDER / PLAYBLAST (HIDE PUSHER IN VIEWPORT TOO)
    # ---------------------------------------------------------
    # Make sure pusher is invisible in viewport for playblast
    if cmds.objExists("Side_Pusher"):
        try:
            cmds.setAttr("Side_Pusher.visibility", 0)
        except:
            pass

    response = cmds.confirmDialog(
        title='Project 5',
        message='Done! Render or Playblast?',
        button=['Playblast', 'Render', 'Close'],
        defaultButton='Playblast',
        cancelButton='Close',
        dismissString='Close'
    )

    if response == 'Playblast':
        fmt = 'qt' if cmds.about(os=True) == 'mac' else 'avi'
        path = cmds.internalVar(userTmpDir=True) + "Domino_Reveal"
        cmds.playblast(
            format=fmt,
            filename=path,
            forceOverwrite=True,
            sequenceTime=0,
            clearCache=1,
            viewer=1,
            showOrnaments=1,
            fp=4,
            percent=100
        )
        
    elif response == 'Render':
        cmds.setAttr("defaultResolution.width", 1280)
        cmds.setAttr("defaultResolution.height", 720)
        cmds.setAttr("defaultRenderGlobals.imageFormat", 8) 
        cmds.render(cam_name, x=1280, y=720)

# EXECUTE
run_stable_dominoes()
