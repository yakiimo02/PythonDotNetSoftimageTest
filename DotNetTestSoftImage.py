"""
Python.Net Softimage Test
.
References:
        http://tech-artists.org/wiki/PythonNetInMaya
        http://shaderop.com/2011/04/using-wxpython-with-autodesk-softimage/

Tested on Softimage 2012 32-bit (No SPs applied.)

Notes:
        Python.NET runs as a Modal dialog in its own GUI thread. If I run
        Softimage script commands such as Application.SelectObj in the
        GUI thread, I get com related errors. I tried avoiding the errors by
        pushing commands onto a command queue and processing the commands
        in the main Softimage thread inside a EventTimer callback and it
        mostly works, but even when called from the Main Thread
        Application.DeleteObj still gives me a com error. Maybe I can't
        call this command from inside a EventTimer callback?

written on 2011/09/30
by yakiimo02

"""

from win32com.client import constants
import clr
import sys
import threading
import time

# Change path to your actual PythonDotNetTest.dll
sys.path.append("C:\\PythonDotNetTest\\PythonDotNetTest\\bin\\Release")
clr.AddReference("PythonDotNetTest")
import PythonDotNetTest

# fifo command queue code
# doesn't block for result so not appropriate for commands that return values.

commandQueue = []
commandQueueLock = threading.RLock()

def queueCommand(callable, arguments=()):
    ''' add function and argments to the commandQueue from the gui thread. '''
    commandQueueLock.acquire()
    commandQueue.append((callable, arguments))
    commandQueueLock.release()

def processGUICommands():
    ''' processGUICommands from the main thread. '''
    #print "processGUICommands: ", threading.current_thread().name
    command = None
    commandQueueLock.acquire()
    if commandQueue:
        command = commandQueue.pop(0)
    commandQueueLock.release()

    if command is not None:
        Application.DeleteObject("sphere")
        print "commandname: " + str(command)
        command[0].__call__(*command[1])


# DotNetTest code

class DotNetTest():

    def __init__(self):
        """ Create the Test WinForm and register event handlers. """
        self.wf = PythonDotNetTest.TestForm()
        self.wf.makeSphereBtn.Click += self.makeSphere
        self.wf.makeCubeBtn.Click += self.makeCube
        self.wf.updateGeomInfoBtn.Click += self.updateGeometryInfo
        self.wf.dataGridView.CellValueChanged += self.dataGridView_CellValueChanged
        self.wf.dataGridView.UserDeletedRow += self.dataGridView_UserDeletedRow
        self.wf.dataGridView.SelectionChanged += self.dataGridView_SelectionChanged

    def show(self):
        """ Display a Modal WinForm. """
        self.wf.ShowDialog()

    def makeSphere(self,*args):
        def sphereCmd():
            # this call results in com error if called from the non-Softimage GUIThread.
            # Application.CreatePrim("Sphere", "MeshSurface", "", "")
            # this call works from a non-Softimage GUIThread
            Application.ActiveSceneRoot.AddGeometry('Sphere', 'MeshSurface')
        sphereCmd()

    def makeCube(self,*args):
        def cubeCmd():
            Application.ActiveSceneRoot.AddGeometry('Cube', 'MeshSurface')
        cubeCmd()

    def updateGeometryInfo(self,*args):
        """ Update the Test WinForm DataGridView with the Softimage scene's geometryShape translation information. """
        self.wf.dataGridView.Rows.Clear()
        sceneRoot = Application.ActiveSceneRoot
        children = sceneRoot.FindChildren2( "", constants.siPolyMeshType, constants.siMeshFamily, True )
        for child in children:
            vTrans = child.Kinematics.Local.GetTransform2(None).Translation
            self.wf.AddRow( child.FullName, vTrans.X, vTrans.Y, vTrans.Z )

    def dataGridView_CellValueChanged(self, sender, eventArgs):
        """ Update the the Softimage scene's geometryShape translation information. """
        name = self.wf.dataGridView.Rows[eventArgs.RowIndex].Cells[0].Value
        newVal = self.wf.dataGridView.Rows[eventArgs.RowIndex].Cells[eventArgs.ColumnIndex].Value
        child = Application.ActiveSceneRoot.FindChild2( name, constants.siPolyMeshType, constants.siMeshFamily, True )
        if child:
            transform = child.Kinematics.Local.GetTransform2(None)
            translation = transform.Translation
            if eventArgs.ColumnIndex == 1:
                transform.Translation = XSIMath.CreateVector3( newVal, translation.Y, translation.Z )
                child.Kinematics.Local.PutTransform2(None,transform)
            elif eventArgs.ColumnIndex == 2:
                transform.Translation = XSIMath.CreateVector3( translation.X, newVal, translation.Z )
                child.Kinematics.Local.PutTransform2(None,transform)
            elif eventArgs.ColumnIndex == 3:
                transform.Translation = XSIMath.CreateVector3( translation.X, translation.Y, newVal )
                child.Kinematics.Local.PutTransform2(None,transform)
        else:
            print "DataGridView_CellValueChanged: " + child + " not found!"

    def dataGridView_UserDeletedRow(self, send, eventArgs):
        """ Delete geometryShape from the Softimage scene. """
        name = eventArgs.Row.Cells[0].Value
        #print "Application.DeleteObj: " + name
        queueCommand(Application.DeleteObj, (name))

    def dataGridView_SelectionChanged(self, sender, eventArgs):
        """ Select the selected geometryShape in the Sofimage scene. """
        # Clear previous selection only if new rows have been selected.
        if self.wf.dataGridView.SelectedRows.Count > 0:
            queueCommand(Application.SelectObj, ("", "", True))
        selectedNames = ""
        for row in self.wf.dataGridView.SelectedRows:
            name = row.Cells[0].Value
            selectedNames += ( name + "," )
        if selectedNames:
            queueCommand(Application.SelectObj,(selectedNames, "", True))

def runDotNetTest():
    """ Run the Test WinForm in a separate GUI Thread. """
    def runDotNetTestThreaded():
        print "GUIThread begin!"
        test = DotNetTest()
        test.show()
        print "GUIThread finished!"
    guiThread = threading.Thread( target = runDotNetTestThreaded, args = (), name="GUIThread" )
    guiThread.start()

# Softimage Plugin related code.

def XSILoadPlugin(in_reg):
    in_reg.Author = "yakiimo02"
    in_reg.Name = "DotNetTest"
    in_reg.Major = 1
    in_reg.Minor = 0

    in_reg.RegisterCommand("DotNetTest","DotNetTest")
    in_reg.RegisterMenu(constants.siMenuMainWindowID,
            "DotNetTest_Menu",
            False,
            False)

    in_reg.RegisterTimerEvent("ProcessDotNetCommands", 100, 0)

    #RegistrationInsertionPoint - do not remove this line

    return True

def XSIUnloadPlugin(in_reg):
    strPluginName = in_reg.Name
    return True

def DotNetTest_Init(in_ctxt):
    oCmd = in_ctxt.Source
    oCmd.Description = "Python.NET Test"
    oCmd.ReturnValue = True
    return True

def DotNetTest_Execute():
    runDotNetTest()
    return True

def DotNetTest_Menu_Init( in_ctxt ):
    oMenu = in_ctxt.Source
    oMenu.AddCommandItem("DotNetTest","DotNetTest")
    return True

def ProcessDotNetCommands_OnEvent( ctxt ):
    result = False
    processGUICommands()
    return result

