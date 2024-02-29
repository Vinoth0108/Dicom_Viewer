import streamlit as st
from src.utils import *
import gc
import numpy as np
from scipy import ndimage
from skimage.transform import resize
# Hide FileUploader deprecation
st.set_option('deprecation.showfileUploaderEncoding', False)

# Hide streamlit header
hide_streamlit_style = """
<style>
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
</style>
"""

st.markdown(hide_streamlit_style, unsafe_allow_html=True) 

data_key = 'has_data'
width = 400
data_is_ready = False
data_has_changed = False

if not os.path.isdir('./data/'):
    os.makedirs('./data/')

if not os.path.isdir('./temp'):
    os.makedirs('./temp/')

# Adjusting images to be centralized.
with open("style.css") as f:
    st.markdown('<style>{}</style>'.format(f.read()), unsafe_allow_html=True)
    
if __name__ == "__main__": 
    
    state = get_state()

    st.title('DICOM Viewer')

    st.sidebar.title('DICOM Image Viewer')

    demo_button = st.sidebar.checkbox('Demo', value=False, key='demo_checkbox')
    
    url_input = st.sidebar.text_input('Enter the Google Drive shared url for the .dcm files', key='url_input')
    
    st.sidebar.markdown('<h5>MAX FILE SIZE: 100 MB</h5>', unsafe_allow_html=True)
    st.sidebar.markdown(' ')
    st.sidebar.markdown('or')

    file_uploaded =  st.sidebar.file_uploader("Upload a .zip with .dcm files (slower than GDrive)", type="zip", key='file_uploader')

    if demo_button:
        url_input = 'https://drive.google.com/file/d/1ESRZpJA92g8L4PqT2adCN3hseFbnw9Hg/view?usp=sharing'

    if file_uploaded:
        if not state[data_key]:
            if does_zip_have_dcm(file_uploaded):
                store_data(file_uploaded)
                data_has_changed = True
    
    if url_input:
        if not state[data_key]:
            if download_zip_from_url(url_input):
                data_has_changed = True

    if st.sidebar.button('---------- Refresh input data ----------', key='refresh_button'):
        clear_data_storage(temp_data_directory + get_report_ctx().session_id + '/')
        clear_data_storage(temp_zip_folder)
        st.caching.clear_cache()
        url_input = st.empty()
        data_is_ready = False
        data_has_changed = False
        state[data_key] = False
        state.clear()

    if data_has_changed:
        valid_folders = get_DCM_valid_folders(temp_data_directory + get_report_ctx().session_id + '/')
        
        for folder in valid_folders:
            state[folder.split('/')[-1]] = ('', '', {'Anomaly': 'Bleeding', 'Slices': ''})

        state[data_key] = True
        state['valid_folders'] = valid_folders
        state.last_serie = ''

        data_has_changed = False
    
    if state[data_key]:
        data_is_ready = True
    
    if data_is_ready:
        series_names = get_series_names(state['valid_folders'])
        
        selected_serie = st.selectbox('Select a series', series_names, index=0, key='select_series')

        st.markdown('<h2>Patient Info</h2>', unsafe_allow_html=True)
        display_info = st.checkbox('Display data', value=True)

        if state.last_serie != selected_serie:
            st.caching.clear_cache()
            state.last_serie = selected_serie

        img3d, info = processing_data(state['valid_folders'][series_names.index(selected_serie)] + '/')
            
        if display_info:
            st.dataframe(info)
        
        slice_slider = st.slider(
            'Slices',
            0, img3d.shape[2] - 1, (img3d.shape[2] - 1)//2,
            key='slice_slider'
        )

        color_threshold = st.slider(
            'Color Threshold',
            0, 100, 50,
            key='color_threshold_slider'
        )
        def rotate_and_resize(image, angle, size):
            rotated = ndimage.rotate(image, angle)
            resized = resize(rotated, size)
            return resized

        axial_max = int(img3d[:, :, slice_slider].max())
        axial_threshold = axial_max * ((2 * color_threshold / 100) - 1)
        axial_slice = normalize_image(filter_image(axial_threshold, img3d[:, :, slice_slider]))

        coronal_max = int(img3d[slice_slider, :, :].max())
        coronal_threshold = coronal_max * ((2 * color_threshold / 100) - 1)
        coronal_slice = normalize_image(filter_image(coronal_threshold, rotate_and_resize(img3d[slice_slider, :, :], 90, (img3d.shape[0], img3d.shape[0]))))

        sagittal_max = int(img3d[:, slice_slider, :].max())
        sagittal_threshold = sagittal_max * ((2 * color_threshold / 100) - 1)
        sagittal_slice = normalize_image(filter_image(sagittal_threshold, rotate_and_resize(img3d[:, slice_slider, :], 90, (img3d.shape[0], img3d.shape[0]))))

        #  Display the slices horizontally
        st.image([axial_slice, coronal_slice, sagittal_slice], caption=['Axial Slice {}'.format(slice_slider), 'Coronal Slice {}'.format(slice_slider), 'Sagittal Slice {}'.format(slice_slider)], width=width)
        
        
       

        st.sidebar.markdown('<h1 style=\'font-size:0.65em\'> Example of annotation with slices: 0-11; 57-59; 112; </h1> ', unsafe_allow_html=True)

        state[selected_serie][2]['Anomaly'] = st.sidebar.text_input('Anomaly Label', value=state[selected_serie][2]['Anomaly'], key='anomaly_label')

        state[selected_serie][2]['Slices'] = st.sidebar.text_input("Axial Annotation - Slices with Anomaly", value=state[selected_serie][2]['Slices'], key='axial_annotation_input')

        annotation_selected = st.sidebar.multiselect('Annotated series to be included in the .json', series_names, series_names, key='annotation_multiselect')
        json_selected = {serie: state[serie][2] for serie in annotation_selected}
        
        if st.checkbox('Check Annotations.json', value=True):
            st.write(json_selected)
        
        download_button_str = download_button(json_selected, 'Annotation.json', 'Download Annotation.json')
        st.sidebar.markdown(download_button_str, unsafe_allow_html=True) 

        del img3d, info

    if st.sidebar.checkbox('Notes', value=True, key='notes_checkbox'):
        st.sidebar.markdown('1. It does not recognize zip folders inside other zip folders.')
        st.sidebar.markdown('2. It only recognizes series with two or more .dcm files.')
        st.sidebar.markdown('3. You can use the arrow keys to change the slider widgets.')
        st.sidebar.markdown('3. Uploaded files are cached until the heroku session becomes idle (30 min).'
                            ' Then, they are automatically deleted.')
        st.sidebar.markdown('4. If you want to manually reset/delete previously uploaded data via URL, ' 
                            'clear the text input, and press the button to refresh input data. '
                            'In case you are using the File Uploader widget, perform the same '
                            'actions described above and then refresh the page with F5. ')
    
    gc.collect()
    state.sync()


